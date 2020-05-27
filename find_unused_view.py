import lkml
import glob
import re
import argparse
import pandas as pd
import os


def path_file_parser(path, extension="", recursive=True):
    """Return a list of Full File Paths
    Parameters:
    path (str): Parent Directory to parse
    extension (Optional) (str): fil e extension to search, i.e. ".txt"
    recursive (Boolan): Defaults to false to check child directories
    """
    return [f for f in glob.glob(path + "**/*" + extension, recursive=recursive)]


def all_explores(path):
    """Return a dictionary of Explores and Joined in Views Objects
    Parameters:
    path (str): Parent Directory to parse
    """
    files = path_file_parser(path, extension='model.lkml')
    files.extend(path_file_parser(path, extension='explore.lkml'))
    models = {}
    for file in files:
        filename = file[file.rfind('/') + 1:]
        models[filename] = {}
        with open(file, 'r') as f:
            try:
                parsed = lkml.load(f)
                try:
                    for explores in parsed['explores']:
                        if 'label' in explores:
                            key = explores['label']
                        else:
                            key = explores['name']
                        
                        if 'view_name' in explores:
                            base_table = explores['view_name']
                        elif 'from' in explores:
                            base_table = explores['from']
                        else:
                            base_table = explores['name']
                        models[filename][key] = [base_table]
                        if 'view_name' in explores and 'from' in explores:
                            models[filename][key].append(explores['from'])
                        # Check if the base table has joins
                        if 'joins' in explores:
                            for join in explores['joins']:
                                if 'view_name' in join and 'from' in join:
                                    models[filename][key].append(join['view_name'])
                                    models[filename][key].append(join['from'])
                                elif 'view_name' in join:
                                    models[filename][key].append(join['view_name'])
                                elif 'from' in join:
                                    models[filename][key].append(join['from'])
                                else:
                                    models[filename][key].append(join['name'])
                except KeyError:
                    print(filename)
            except SyntaxError:
                print(filename)
    return models


def all_views(path):
    """Return a dictionary of Views and Dependent View Objects
    Parameters:
    path (str): Parent Directory to parse'
    """
    files = path_file_parser(path, extension='view.lkml')
    views = {}
    for file in files:
        filename = file[file.rfind('/') + 1:]
        views[filename] = {}
        with open(file, 'r') as f:
            try:
                parsed = lkml.load(f)
                try:
                    for view in parsed['views']:
                        views[filename][view['name']] = []
                        if 'derived_table' in view:
                            if 'sql' in view['derived_table']:
                                regex = "([A-Za-z0-9_]+)\.SQL_TABLE_NAME"
                                matches = re.findall(regex, view['derived_table']['sql'])
                                [views[filename][view['name']].append(match) for match in matches]
                        if 'extends' in view:
                            [views[filename][view['name']].append(e) for e in view['extends']]
                except KeyError:
                    print(filename)
            except SyntaxError:
                print(filename)
            except KeyError:
                print(filename)
    return views


def set_unique_explores(model_dict):
    """Return a set of unique explores
    Parameters:
    model_dict (dict): Explore Directory to parse'
    """
    return set([v for explores in model_dict.values() for views in explores.values() for v in views])


def set_unique_views(view_dict):
    """Return a set of unique views
    Parameters:
    view_dict (dict): Views Directory to parse'
    """
    set_view = set()
    for views in view_dict.values():
        for view_name, view_reference in views.items():
            if len(view_reference) > 0:
                set_view.update(set(view_reference))
            set_view.add(view_name)
    return set_view


def identify_dependent_view(view_dict):
    """Return a set of view dictionaries that have dependencies
    Parameters:
    view_dict (dict): Views Directory to parse'
    """
    return {k: v for view in view_dict.values() for k, v in view.items() if len(v) > 0}


def dependent_view_check(view_dict, unique_explores_set):
    for view in view_dict:
        if view in unique_explores_set:
            for reference in view_dict[view]:
                if reference not in unique_explores_set:
                    unique_explores_set.add(reference)
                    if reference in view_dict:
                        dependent_view_check(view_dict, unique_explores_set)


def find_unused_views(set_views, set_explores):
    """ Return a set of view dictionaries that have dependencies
    Parameters:
    set_views (set): Unique Views
    set_explores (set): Unique Exploers
    """
    unused_views = list(set_views - set_explores)
    return sorted(unused_views)


def find_empty_files(input_dict):
    """ Return a set of view dictionaries that have dependencies
    Parameters:
    set_views (set): Unique Views
    set_explores (set): Unique Exploers
    """
    return [file_name for file_name, name in input_dict.items() if len(name) == 0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Find all view files that are not referenced in content in a project.')
    parser.add_argument('--path', '-p', type=str, required=True, help='A path to be parsed')
    args = parser.parse_args()
    # path = '/Users/johndemartino/Downloads/looker-apalon-lookml-master'
    # main_path = args.path[args.path.rfind('/') + 1:]
    main_path = os.path.basename(args.path.split('/')[-2])
    models = all_explores(args.path)
    views = all_views(args.path)
    views_with_dependent = identify_dependent_view(views)

    unique_explores = set_unique_explores(models)
    unique_views = set_unique_views(views)
    dependent_view_check(views_with_dependent, unique_explores)
    unused_views = find_unused_views(unique_views, unique_explores)
    empty_model_files = find_empty_files(models)
    empty_view_files = find_empty_files(views)
    output = pd.Series(unused_views)
    output = output.append(pd.Series(empty_view_files))
    output.reset_index(drop=True).to_csv(main_path + '_unused_views_2.csv', )
