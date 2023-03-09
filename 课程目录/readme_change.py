import os

"""
Input: 绝对路径或当前路径，例如 'D:/picture'
"""


def traverse_dir(current_dir):
    file_list = os.listdir(current_dir)
    for file in file_list:
        path = os.path.join(current_dir, file)
        if os.path.isdir(path):
            # do something to this directory
            with open(path + '/README.md', 'a', encoding='utf-8') as f:
              f.write('<br><h1>资源贡献</h1><br>希望大家能多多贡献资源，促进仓库良性发展，帮助更多的同学考个好成绩！仓库地址：[https://github.com/Xovee/uestc-course](https://github.com/Xovee/uestc-course)<br><br>国内访问GitHub不太稳定，有时候需要特殊手段。有问题可以邮件联系我：xovee at live.com')

              

num_files = traverse_dir('./课程目录/')
