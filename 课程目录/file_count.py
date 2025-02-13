import os

"""
Input: 绝对路径或当前路径，例如 'D:/picture'
"""


def traverse_dir(current_dir, num):
    file_list = os.listdir(current_dir)
    for file in file_list:
        path = os.path.join(current_dir, file)
        if os.path.isdir(path):
            # do something to this directory
            num = traverse_dir(path, num)
        if os.path.isfile(path):
            # do something to this file
            if '.md' not in path:
                num += 1
    return num

def count_num_courses(dir, num):
    file_list = os.listdir(dir)
    for file in file_list:
        path = os.path.join(dir, file)
        if os.path.isdir(path):
            num += 1
    return num


num_files = 0
num_courses = 0

path = './课程目录/'
# path = './考研目录/'

num_files = traverse_dir(path, num_files)

num_courses = count_num_courses(path, num_courses)


print('Number of courses:', num_courses)
print('Number of all course files:', num_files)
