#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) IBM Corporation 2019
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = "Chaitanya Shivade, Tomasz Kornuta"

import string
import tqdm
import pandas as pd
from PIL import Image
from torchvision import transforms

import os
import torch
from torchvision import transforms

from ptp.components.problems.problem import Problem
from ptp.data_types.data_definition import DataDefinition


class VQAMED2019(Problem):
    """
    Problem providing data associated with ImageCLEF VQA 2019 challenge.

    The dataset consists of four splits:

        - a training set of 3,200 medical images with 12,792 Question-Answer (QA) pairs,
        - a validation set of 500 medical images with 2,000 QA pairs, and
        - a test set of 500 medical images with 500 questions.

    Aside of that, there are 4 categories of questions based on:
        - Modality (C1),
        - Plane (C2),
        - Organ System (C3), and
        - Abnormality (C4).

    Please see the readme file of the crowdAI dataset section for more detailed information.
    For more details please refer to the associated _website or _crowdai websites for more details.

    .. _crowdai: https://www.crowdai.org/challenges/imageclef-2019-vqa-med

    .. _website: https://www.imageclef.org/2019/medical/vqa/
    """
    def __init__(self, name, config):
        """
        Initializes problem object. Calls base constructor. Downloads the dataset if not present and loads the adequate files depending on the mode.

        :param name: Name of the component.

        :param class_type: Class type of the component.

        :param config: Dictionary of parameters (read from configuration ``.yaml`` file).
        """
        # Call constructors of parent classes.
        Problem.__init__(self, name, VQAMED2019, config)

        # Get key mappings of all output streams.
        self.key_images = self.stream_keys["images"]
        self.key_image_ids = self.stream_keys["image_ids"]
        self.key_questions = self.stream_keys["questions"]
        self.key_answers = self.stream_keys["answers"]
        self.key_category_ids = self.stream_keys["category_ids"]
        self.key_category_names = self.stream_keys["category_names"]
        self.key_image_sizes = self.stream_keys["image_sizes"]

        # Check the desired image size.
        if len(self.config['resize_image']) != 2:
            self.logger.error("'resize_image' field must contain 2 values: the desired height and width")
            exit(-1)

        # Output image dimensions.
        self.height = self.config['resize_image'][0]
        self.width = self.config['resize_image'][1]
        self.depth = 3

        # Set global variables - all dimensions ASIDE OF BATCH.
        self.globals["image_height"] = self.height
        self.globals["image_width"] = self.width
        self.globals["image_depth"] = self.depth

        # Those values will be used to rescale the image_sizes to range (0, 1).
        self.scale_image_height = self.config['scale_image_size'][0]
        self.scale_image_width = self.config['scale_image_size'][1]

        # Set parameters and globals related to categories.
        self.globals["num_categories"] = 6
        self.globals["category_word_mappings"] = {'C1': 0, 'C2': 1, 'C3': 2, 'C4': 3, 'BINARY': 4, '<UNK>': 5}
        self.category_idx_to_word = {0: 'C1', 1: 'C2', 2: 'C3', 3: 'C4', 4: 'BINARY', 5: '<UNK>'}

        # Check if we want to remove punctuation from questions/answer
        self.remove_punctuation = self.config["remove_punctuation"]

        # Get the absolute path.
        self.data_folder = os.path.expanduser(self.config['data_folder'])

        # Set split-dependent data.
        if self.config['split'] == 'training':
            self.split_folder = os.path.join(self.data_folder, "ImageClef-2019-VQA-Med-Training")
            self.image_folder = os.path.join(self.split_folder, 'Train_images')
            # Set source files.
            source_files = [
                "QAPairsByCategory/C1_Modality_train.txt",
                "QAPairsByCategory/C2_Plane_train.txt",
                "QAPairsByCategory/C3_Organ_train.txt",
                "QAPairsByCategory/C4_Abnormality_train.txt"
                ]
            # Set the categories associated with each of those files.
            source_categories = [0, 1, 2, 3]

            # Filter lists taking into account configuration.
            source_files, source_categories = self.filter_sources(source_files, source_categories)

        elif self.config['split'] == 'validation':
            self.split_folder = os.path.join(self.data_folder, "ImageClef-2019-VQA-Med-Validation")
            self.image_folder = os.path.join(self.split_folder, 'Val_images')
            # Set source files.
            source_files = [
                "QAPairsByCategory/C1_Modality_val.txt",
                "QAPairsByCategory/C2_Plane_val.txt",
                "QAPairsByCategory/C3_Organ_val.txt",
                "QAPairsByCategory/C4_Abnormality_val.txt"
                ]
            # Set the categories associated with each of those files.
            source_categories = [0, 1, 2, 3]

            # Filter lists taking into account configuration.
            source_files, source_categories = self.filter_sources(source_files, source_categories)

        # Load dataset.
        self.logger.info("Loading dataset from files:\n {}".format(source_files))
        self.dataset = self.load_dataset(source_files, source_categories)
        self.logger.info("Loaded dataset consisting of {} samples".format(len(self.dataset)))

        # Display exemplary sample.
        self.logger.info("Exemplary sample:\n [ category: {}\t image_ids: {}\t question: {}\t answer: {} ]".format(
            self.dataset[0][self.key_image_ids],
            self.dataset[0][self.key_questions],
            self.dataset[0][self.key_answers],
            self.dataset[0][self.key_category_ids]
            ))

    def filter_sources(self, source_files, source_categories):
        """
        Loads the dataset from one or more files.

        :param source_files: List of source files.

        :param source_categories: List of categories associated with each of those files. (<UNK> unknown)

        :return: Tuple consisting of: filtered source_files and filtered source_categories
        """
        # Check categories that user want to use.
        use_files = [False] * 4
        categs = {'C1': 0, 'C2': 1, 'C3': 2, 'C4': 3}
        for cat in self.config["categories"].replace(" ","").split(","):
            # "Special" case.
            if cat == "all":
                use_files = [True] * 4
                # Make no sense to continue.
                break
            else:
                if cat in categs.keys():
                    use_files[categs[cat]] = True
        # Filter.
        _, source_files, source_categories = zip(*(filter(lambda x: x[0], zip(use_files, source_files,source_categories))))
        return source_files, source_categories


    def load_dataset(self, source_files, source_categories):
        """
        Loads the dataset from one or more files.

        :param source_files: List of source files.

        :param source_categories: List of categories associated with each of those files. (<UNK> unknown)
        """
        # Set containing list of tuples.
        dataset = []

        # Create table used for removing punctuations.
        table = str.maketrans({key: None for key in string.punctuation})

        # Process files with categories.
        for data_file, category in zip(source_files, source_categories):
            # Set absolute path to file.
            data_file = os.path.join(self.split_folder, data_file)
            self.logger.info('Loading dataset from {} (category: {})...'.format(data_file, category))
            # Load file content using '|' separator.
            df = pd.read_csv(filepath_or_buffer=data_file, sep='|',header=None,
                    names=[self.key_image_ids,self.key_questions,self.key_answers])

            # Add tdqm bar.
            t = tqdm.tqdm(total=len(df.index))
            for _, row in df.iterrows():
                # Retrieve question and answer.
                question = row[self.key_questions]
                answer = row[self.key_answers]

                # Process question - if required.
                if self.remove_punctuation in ["questions","all"]:
                    question = question.translate(table)

                # Process answer - if required.
                if self.remove_punctuation in ["answers","all"]:
                    answer = answer.translate(table)

                # Add record to dataset.
                dataset.append({
                    self.key_image_ids: row[self.key_image_ids],
                    self.key_questions: question,
                    self.key_answers: answer,
                    # Add category.
                    self.key_category_ids: category
                    })

                t.update()
            t.close()

        # Return the created list.
        return dataset

    def __len__(self):
        """
        Returns the "size" of the "problem" (total number of samples).

        :return: The size of the problem.
        """
        return len(self.dataset)


    def output_data_definitions(self):
        """
        Function returns a dictionary with definitions of output data produced the component.

        :return: dictionary containing output data definitions (each of type :py:class:`ptp.utils.DataDefinition`).
        """
        return {
            self.key_indices: DataDefinition([-1, 1], [list, int], "Batch of sample indices [BATCH_SIZE] x [1]"),
            self.key_images: DataDefinition([-1, self.depth, self.height, self.width], [torch.Tensor], "Batch of images [BATCH_SIZE x IMAGE_DEPTH x IMAGE_HEIGHT x IMAGE_WIDTH]"),
            self.key_image_ids: DataDefinition([-1, 1], [list, str], "Batch of image names, each being a single word [BATCH_SIZE] x [STRING]"),
            self.key_image_sizes: DataDefinition([-1, 2], [torch.Tensor], "Batch of original sizes (height, width) of images [BATCH_SIZE x 2]"),
            self.key_questions: DataDefinition([-1, 1], [list, str], "Batch of questions, each being a string consisting of many words [BATCH_SIZE] x [STRING]"),
            self.key_answers: DataDefinition([-1, 1], [list, str], "Batch of target answers, each being a string consisting of many words [BATCH_SIZE] x [STRING]"),
            self.key_category_ids: DataDefinition([-1], [torch.Tensor], "Batch of target category indices, each being a single index [BATCH_SIZE]"),
            self.key_category_names: DataDefinition([-1, 1], [list, str], "Batch of category target names, each being a single word [BATCH_SIZE] x [STRING]"),
            }


    def __getitem__(self, index):
        """
        Getter method to access the dataset and return a single sample.

        :param index: index of the sample to return.
        :type index: int

        :return: DataDict({'indices', 'images', 'images_ids','questions', 'answers', 'category_ids', 'image_sizes'})
        """
        # Get item.
        item = self.dataset[index]

        # Load the adequate image.
        img_id = item[self.key_image_ids]
        extension = '.jpg'
        # Load the image.
        img = Image.open(os.path.join(self.image_folder, img_id + extension))
        # Get its width and height.
        width, height = img.size

        if(self.config['use_augmentation'] == 'True'):
            rotate = (-45, 135)
            translate = (0.05, 0.25)
            scale = (0.5, 2)
            transforms_list = [transforms.RandomAffine(rotate, translate, scale), transforms.RandomHorizontalFlip()]
        else:
            transforms_list = []
        # Resize the image and transform to Torch Tensor.
        transforms_com = transforms.Compose(transforms_list + [
                transforms.Resize([self.height,self.width]),
                transforms.ToTensor(),
                # Use normalization that the pretrained models from TorchVision require.
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                ])
        img = transforms_com(img) #.type(torch.FloatTensor).squeeze()

        #print("img: min_val = {} max_val = {}".format(torch.min(img),torch.max(img)) )

        # Create the resulting sample (data dict).
        data_dict = self.create_data_dict(index)

        # Image related variables.
        data_dict[self.key_images] = img
        data_dict[self.key_image_ids] = img_id
        # Scale width and height to range (0,1).
        data_dict[self.key_image_sizes] = torch.FloatTensor([float(height/self.scale_image_height), float(width/self.scale_image_width)])

        # Question.
        data_dict[self.key_questions] = item[self.key_questions]
        data_dict[self.key_answers] = item[self.key_answers]

        # Question category related variables.
        # Check if this is binary question.
        if self.predict_yes_no(item[self.key_questions]):
            data_dict[self.key_category_ids] = 4 # Binary.
            data_dict[self.key_category_names] = self.category_idx_to_word[4]
        else:
            data_dict[self.key_category_ids] = item[self.key_category_ids]
            data_dict[self.key_category_names] = self.category_idx_to_word[item[self.key_category_ids]]

        # Return sample.
        return data_dict

    def predict_yes_no(self, qtext):
        """
        Determines whether this is binary (yes/no) type of question.
        """
        yes_no_starters = ['is','was','are','does']
        tokens = qtext.split(' ')
        first_token = tokens[0]
        if first_token in yes_no_starters and ('or' not in tokens):
            return True
        return False

    def collate_fn(self, batch):
        """
        Combines a list of DataDict (retrieved with :py:func:`__getitem__`) into a batch.

        :param batch: list of individual samples to combine
        :type batch: list

        :return: DataDict({'indices', 'images', 'images_ids','questions', 'answers', 'category_ids', 'image_sizes'})

        """
        # Collate indices.
        data_dict = self.create_data_dict([sample[self.key_indices] for sample in batch])

        # Stack images.
        data_dict[self.key_images] = torch.stack([item[self.key_images] for item in batch]).type(torch.FloatTensor)
        data_dict[self.key_image_ids] = [item[self.key_image_ids] for item in batch]
        data_dict[self.key_image_sizes] = torch.stack([item[self.key_image_sizes] for item in batch]).type(torch.FloatTensor)

        # Collate lists.
        data_dict[self.key_questions] = [item[self.key_questions] for item in batch]
        data_dict[self.key_answers] = [item[self.key_answers] for item in batch]

        # Stack categories.
        data_dict[self.key_category_ids] = torch.tensor([item[self.key_category_ids] for item in batch])
        data_dict[self.key_category_names] = [item[self.key_category_names] for item in batch]

        # Return collated dict.
        return data_dict
