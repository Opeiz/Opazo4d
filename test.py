import os

def main():
    def print_directory_tree(root_dir):
        """
        Recursively prints the directory tree starting at root_dir
        """
        for root, dirs, files in os.walk(root_dir):
            level = root.replace(root_dir, '').count(os.sep)
            indent = ' ' * 4 * (level)
            print('{}{}/'.format(indent, os.path.basename(root)))
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                print('{}{}'.format(subindent, f))

    root_dir = '/homes/j22opazo/Documents/Stage/Opazo4d'
    print_directory_tree(root_dir)

if __name__ == '__main__':
    main()