import os
import importlib

def main():
    def get_used_files(main_file):
        used_files = set()

        def explore_dependencies(file_path):
            """
            Recursively explore the dependencies of file_path and add them to used_files
            """
            if file_path in used_files:
                return

            used_files.add(file_path)

            with open(file_path) as f:
                content = f.read()

            for line in content.split('\n'):
                if line.startswith('from') or line.startswith('import'):
                    parts = line.split()
                    module_name = parts[1]
                    try:
                        module_path = importlib.import_module(module_name).__name__
                        if os.path.isfile(module_path):
                            explore_dependencies(module_path)
                    except ModuleNotFoundError:
                        pass

        explore_dependencies(os.path.abspath(main_file))

        return used_files
    
    main_file = '/homes/j22opazo/Documents/Stage/Opazo4d/main.py' 
    used_files = get_used_files(main_file)

    for file_path in used_files:
        print(file_path)

if __name__ == '__main__':
    main()