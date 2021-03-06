#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) IBM Corporation 2018
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

import os
import yaml

from ptp.utils.app_state import AppState


def display_parsing_results(logger, parsed_args, unparsed_args):
    """
    Displays the properly & improperly parsed arguments (if any).

    :param logger: logger object

    :param parsed_args: Parsed command-line arguments

    :param unparsed_args: Unparsed command-line arguments

    """
    # Log the parsed flags.
    flags_str = 'Properly parsed command line arguments: \n'
    flags_str += '='*80 + '\n'
    for arg in vars(parsed_args): 
        flags_str += "  {}= {} \n".format(arg, getattr(parsed_args, arg))
    flags_str += '='*80 + '\n'
    logger.info(flags_str)

    # Log the unparsed flags if any.
    if unparsed_args:
        flags_str = 'Invalid command line arguments: \n'
        flags_str += '='*80 + '\n'
        for arg in unparsed_args: 
            flags_str += "  {} \n".format(arg)
        flags_str += '='*80 + '\n'
        logger.warning(flags_str)


    # Display results of parsing - add before export!
    #self.display_parsing_results(logger)

def export_experiment_configuration_to_yml(logger, log_dir, filename, config_interface_obj, user_confirm):
    """
    Dumps the configuration to ``yaml`` file.

    :param logger: logger object

    :param log_dir: Directory used to host log files (such as the collected statistics).
    :type log_dir: str

    :param filename: Name of the ``yaml`` file to write to.
    :type filename: str

    :param config_interface_obj: Configuration interface object.

    :param user_confirm: Whether to request user confirmation.
    :type user_confirm: bool

    """
    # -> At this point, all configuration for experiment is complete.


    # Log the resulting training configuration.
    conf_str = 'Final parameter registry configuration:\n'
    conf_str += '='*80 + '\n'
    conf_str += yaml.safe_dump(config_interface_obj.to_dict(), default_flow_style=False)
    conf_str += '='*80 + '\n'
    
    logger.info(conf_str)

    # Save the resulting configuration into a .yaml settings file, under log_dir
    with open(log_dir + filename, 'w') as yaml_backup_file:
        yaml.dump(config_interface_obj.to_dict(), yaml_backup_file, default_flow_style=False)

    # Ask for confirmation - optional.
    if user_confirm:
        try:
            input('Press <Enter> to confirm and start the experiment\n')
        except KeyboardInterrupt:
            exit(0)            


def load_class_default_config_file(class_type):
    """
    Function loads default configuration from the default config file associated with the given class type and adds it to parameter registry.

    :param class_type: Class type of a given object.

    :raturn: Loaded default configuration.
    """
    
    # Extract path to default config.
    module = class_type.__module__.replace(".","/")
    rel_path = module[module.find("ptp")+4:]
    # Build the abs path to the default config file of a given component.
    abs_default_config = AppState().absolute_config_path + "default/" + rel_path + ".yml"

    # Check if file exists.
    if not os.path.isfile(abs_default_config):
        print("ERROR: The default configuration file '{}' for '{}' component does not exist".format(abs_default_config, class_type.__module__))
        exit(-1)

    try:
        # Open file and get parameter dictionary.
        with open(abs_default_config, 'r') as stream:
            param_dict = yaml.safe_load(stream)

        # Return default parameters so they can be added to the global registry.
        if param_dict is None:
                print("WARNING: The default configuration file '{}' is empty!".format(abs_default_config))
                return {}
        else:
            return param_dict

    except yaml.YAMLError as e:
        print("ERROR: Couldn't properly parse the '{}' default configuration file. YAML error:\n  {}".format(abs_default_config, e))
        exit(-2)


def recurrent_config_parse(configs: str, configs_parsed: list, abs_config_path: str):
    """
    Parses names of configuration files in a recursive manner, i.e. \
    by looking for ``default_config`` sections and trying to load and parse those \
    files one by one.

    :param configs: String containing names of configuration files (with paths), separated by comas.
    :type configs: str

    :param configs_parsed: Configurations that were already parsed (so we won't parse them many times).
    :type configs_parsed: list

    :param abs_config_path: Absolute path to ``config`` directory.

    :return: list of parsed configuration files.

    """
    # Split and remove spaces.
    configs_to_parse = configs.replace(" ", "").split(',')

    # Terminal condition.
    while len(configs_to_parse) > 0:

        # Get config.
        config = configs_to_parse.pop(0)
        abs_config = abs_config_path + config

        # Skip empty names (after lose comas).
        if config == '':
            continue
        print("Info: Parsing the {} configuration file".format(abs_config))

        # Check if it was already loaded.
        if config in configs_parsed:
            print('Warning: Configuration file {} already parsed - skipping'.format(abs_config))
            continue

        # Check if file exists.
        if not os.path.isfile(abs_config):
            print('Error: Configuration file {} does not exist'.format(abs_config))
            exit(-1)

        try:
            # Open file and get parameter dictionary.
            with open(abs_config, 'r') as stream:
                param_dict = yaml.safe_load(stream)
        except yaml.YAMLError as e:
            print("Error: Couldn't properly parse the {} configuration file".format(abs_config))
            print('yaml.YAMLERROR:', e)
            exit(-1)

        # Remember that we loaded that config.
        configs_parsed.append(config)

        # Check if there are any default configs to load.
        if 'default_configs' in param_dict:
            # If there are - recursion!
            configs_parsed = recurrent_config_parse(
                param_dict['default_configs'], configs_parsed, abs_config_path)

    # Done, return list of loaded configs.
    return configs_parsed


def reverse_order_config_load(config_interface_obj, configs_to_load, abs_config_path):
    """
    Loads configuration files in reversed order.

    :param config_interface_obj: Configuration interface object.

    :param configs_to_load: list of configuration files to load (relative to config directory)

    :param abs_config_path: Absolute path to config directory.

    """
    for config in reversed(configs_to_load):
        # Load config from YAML file.
        config_interface_obj.add_config_params_from_yaml(abs_config_path + config)
        print('Info: Loaded configuration from file {}'.format(abs_config_path + config))
