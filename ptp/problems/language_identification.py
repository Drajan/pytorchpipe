# Copyright (C) tkornuta, IBM Corporation 2019
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

__author__ = "Tomasz Kornuta"

import os

from ptp.utils.problem import Problem
from ptp.utils.data_definition import DataDefinition


class LanguageIdentification(Problem):
    """
    Language identification (classification) problem.
    """

    def __init__(self, name, params):
        """
        Initializes problem object. Calls base constructor.

        :param name: Name of the component.

        :param params: Dictionary of parameters (read from configuration ``.yaml`` file).
        """
        # Call constructors of parent classes.
        Problem.__init__(self, name, params)

        # Set key mappings.
        self.key_inputs = self.mapkey("inputs")
        self.key_targets = self.mapkey("targets")

        # Set default parameters.
        self.params.add_default_params({'data_folder': '~/data/language_identification',
                                        'use_train_data': True
                                        })
        # Get absolute path.
        self.data_folder = os.path.expanduser(self.params['data_folder'])
        
        # Retrieve parameters from the dictionary.
        self.use_train_data = self.params['use_train_data']

        # Set empty inputs and targets.
        self.inputs = []
        self.targets = []


    def output_data_definitions(self):
        """ 
        Function returns a dictionary with definitions of output data produced the component.

        :return: dictionary containing output data definitions (each of type :py:class:`ptp.utils.DataDefinition`).
        """
        return {
            self.key_inputs: DataDefinition([-1, 1], [list, str], "Batch of sentences, each being a single string (many words) [BATCH_SIZE x SENTENCE]"),
            self.key_targets: DataDefinition([-1, 1], [list, str], "Batch of targets, each being a single label (word) BATCH_SIZE x WORD]")
            }


    def __getitem__(self, index):
        """
        Getter method to access the dataset and return a sample.

        :param index: index of the sample to return.
        :type index: int

        :return: ``DataDict({'inputs','targets'})``

        """
        # Return data_dict.
        data_dict = self.create_data_dict(index)
        data_dict[self.key_inputs] = self.inputs[index]
        data_dict[self.key_targets] = self.targets[index]
        return data_dict
