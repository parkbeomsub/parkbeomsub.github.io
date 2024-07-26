import os

def remove_spaces_in_filenames(directory):
    for filename in os.listdir(directory):
        # 현재 파일의 전체 경로
        old_file_path = os.path.join(directory, filename)
        
        # 파일명에서 띄어쓰기 제거
        new_filename = filename.replace(' ', '')
        new_file_path = os.path.join(directory, new_filename)
        
        # 파일명 변경
        os.rename(old_file_path, new_file_path)
        print(f"Renamed: {old_file_path} -> {new_file_path}")

# 사용 예시
directory_path = os.getcwd()  # 파일명이 있는 디렉토리 경로
remove_spaces_in_filenames(directory_path)