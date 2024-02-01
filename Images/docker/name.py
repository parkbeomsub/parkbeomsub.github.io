# image 파일에 띄어쓰기가 있어  이미지를 불러오지 못하는 이슈로 생성

import os

path="./"
file_list = os.listdir(path)

print(file_list)
print(type(file_list[0]))

for i in file_list :
    os.rename(i,i.replace(" ",""))