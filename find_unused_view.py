import lkml
import glob
import re
import argparse
from collections import defaultdict
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


def identify_all_explores(parsed_lookML_file):
    """Return a dictionary of All explores and joined in views objects within a file
    Parameters:
    path (str): Parsed LookML objects
    filename (str): filename for parsed object
    """
    # Check if the base table has joins
    if 'explores' in parsed_lookML_file:
        all_explores = defaultdict(list)
        for explore in parsed_lookML_file['explores']:
            if 'view_name' not in explore and 'from' not in explore:
                all_explores[explore['name']].append(explore['name'])
            if 'view_name' in explore:
                all_explores[explore['name']].append(explore['view_name'])
            if 'from' in explore:
                all_explores[explore['name']].append(explore['from'])
            # Check if the base table has joins
            if 'joins' in explore:
                for join in explore['joins']:
                    all_explores[explore['name']].append(join['name'])
                    if 'view_name' in join:
                        all_explores[explore['name']].append(join['view_name'])
                    if 'from' in join:
                        all_explores[explore['name']].append(join['from'])
        return all_explores


def identify_all_views(parsed_lookML_file):
    """Return a dictionary of all views and dependent view objects
    Parameters:
    path (str): Parent Directory to parse
    filename (str): filename for parsed object
    """
    if 'views' in parsed_lookML_file:
        all_views = defaultdict(list)
        for view in parsed_lookML_file['views']:
            all_views[view['name']].append(view['name'])
            if 'derived_table' in view:
                if 'sql' in view['derived_table']:
                    regex = r"([A-Za-z0-9_]+)\.SQL_TABLE_NAME"
                    matches = re.findall(regex, view['derived_table']['sql'])
                    [all_views[view['name']].append(match) for match in matches]
            if 'extends' in view:
                [all_views[view['name']].append(e) for e in view['extends']]
        return all_views


def set_unique_explores(all_explores_dict):
    """Return a set of unique explores
    Parameters:
    model_dict (dict): Explore Directory to parse'
    """
    return set([view for filename in all_explores_dict for base_view in all_explores_dict[filename] for view in all_explores_dict[filename][base_view]])


def set_unique_views(all_views_dict):
    """Return a set of unique views
    Parameters:
    all_views_dict (dict): Views Directory to parse'
    """
    return set([view for filename in all_views_dict for view_name in all_views_dict[filename] for view in all_views_dict[filename][view_name]])


def dependent_view_check(view_dict, unique_explores_set):
    for view_name in view_dict.values():
        for views in view_name.values():
            if len(views) > 1 and views[0] in unique_explores_set:
                for reference in views[1:]:
                    if reference not in unique_explores_set:
                        unique_explores_set.add(reference)


def find_unused_views(set_views, set_explores):
    """ Return a set of view dictionaries that have dependencies
    Parameters:
    set_views (set): Unique Views
    set_explores (set): Unique Exploers
    """
    unused_views = list(set_views - set_explores)
    return sorted(unused_views)


if __name__ == "__main__":
    # Initialize Argument Parser
    parser = argparse.ArgumentParser(description='Find all view files that are not referenced in content in a project.')
    parser.add_argument('--path', '-p', type=str, required=True, help='A path to be parsed')
    args = parser.parse_args()
    # Find the last directory within path agrument
    last_dir = os.path.basename(args.path.split('/')[-2])
    files = path_file_parser(args.path, extension='*.lkml')
    all_explores = {}
    all_views = {}
    unparsable_lookML_file = []
    for file in files:
        lookML_filename = file[file.rfind('/') + 1:]
        with open(file, 'r') as f:
            try:
                parsed_lookML_file = lkml.load(f)
                explore = identify_all_explores(parsed_lookML_file)
                if explore is not None:
                    all_explores[lookML_filename] = explore
                view = identify_all_views(parsed_lookML_file)
                if view is not None:
                    all_views[lookML_filename] = view
            except SyntaxError:
                unparsable_lookML_file.append(lookML_filename)
    unique_explores = set_unique_explores(all_explores)
    dependent_view_check(all_views, unique_explores)
    unique_views = set_unique_views(all_views)
    unused_views = find_unused_views(unique_views, unique_explores)
    output = pd.Series(unused_views)
    output = output.append(pd.Series(unparsable_lookML_file))
    output.reset_index(drop=True).to_csv(last_dir + '_unused_views.csv', )
