import os

"""
Input: 绝对路径或当前路径，例如 'D:/picture'
"""
def create_file(path):
    with open(path, 'w') as f:
        pass


def traverse_dir(current_dir):
    file_list = os.listdir(current_dir)
    for file in file_list:
        path = os.path.join(current_dir, file)
        if os.path.isdir(path):
            create_file(path + '/README.md')
            traverse_dir(path)
        if os.path.isfile(path):
            pass
            # do something to this file


traverse_dir('./')
