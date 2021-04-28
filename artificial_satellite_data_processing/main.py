# -*- coding: utf-8 -*-
"""
Created on Mon Mar  8 20:05:36 2021

@author: karig
"""
import binascii
import time
import numpy as np

#CRC계산
def cal_CRC(full_data):
    crc = 0xFFFF
    for i in full_data:
        crc = (crc >> 8) | (crc << 8)
        crc ^= i
        crc ^= (crc & 0xFF) >> 4
        crc ^= crc << 12
        crc ^= (crc & 0x00FF) << 5
        crc &= 0xFFFF
    return crc

#CRC검사 결과 1or0
def test_CRC(data,CRC,base = 16):
    crcc = cal_CRC(data[:-2])
    crc = int(binascii.hexlify(CRC),base)
    CRC_result = bool(crcc == crc)
    return CRC_result
    
#변수 길이 데이터 읽기
def read_var_len(payload_name):
    file_name = './payload_length/'+payload_name+'.txt'
    var_len = np.loadtxt(file_name , delimiter = ',', dtype = str)
    len_dic = {}
    for i in var_len:
        len_dic[i[0]] = int(i[1])
    len_sum = 0
    for i in len_dic:
        len_sum+=len_dic[i] #데이터 세트 총 길이(ex. lp: 742)
    return len_dic, len_sum

#0142:sst1~0145:mag
def read_payload_id(file_name):
    file_name = './payload_length/'+file_name+'.txt'
    PI = np.loadtxt(file_name,delimiter = ',', dtype = str)
    PI_dic = {}
    for i in PI:
        PI_dic[i[0]] = i[1]
    return PI_dic

#데이터 세트 분할
def slicing_data(data, embark_id):
    done = False
    PI = str(binascii.hexlify(data[4:6]))[2:-1] #PI구분
    
    PI_SST = embark_id[PI]
    if PI == '0142' or PI == '0143': #10hz or 100hz
        if data[13] == 0:
            PI_SST = PI_SST+'_10'
        if data[13] == 1:
            PI_SST = PI_SST+'_100'
    
    _,len_sum = read_var_len(PI_SST)
    
    sliced_data = data[:len_sum]
    remain_data = data[len_sum:]
    if len(remain_data)<267:
        done = True
    
    return sliced_data, remain_data, PI_SST, done

#하나의 데이터세트 변수별로 분할
def dividing_dataset(one_dataset, PI):
    len_dic,_ = read_var_len(PI)
    data_var_dic = {}
    length_count = 0
    for i in len_dic:
        data_var_dic[i] = one_dataset[length_count:length_count+len_dic[i]]
        length_count += len_dic[i]
    return data_var_dic

# txt출력 함수
def writing_txt(path, OP, PI, ET, dataset, count):
    file_name = path + OP+'_'+PI+'_'+ET[:10]+'_'+count+'.txt' #현재 실행되는 경로에 OP이름_PI이름_EpochTime.txt로 저장
    file = open(file_name, "w")
    for i in dataset:
        file.write(str(dataset[i])+',')
    file.close()

#데이터 쓰기, 형식 변환 클래스
class data_processing:
    def __init__(self, LP_data_list): #LP_data_list: 변수별 데이터, 세트로 배열 
        self.LP_data_list = LP_data_list

    #형식 변환 함수
    def transform(self,embark_dic, epochtime_name = 'ET', operator_name = 'OP', embark_name = 'PI', time_format = '%Y-%m-%d %H:%M:%S'): 
        #탑재체 ID 딕셔너리를 받아서 데이터 변환, time_format: 시간 형식
        count = 0
        for i in self.LP_data_list:
            count +=1
            for j in i:
                if j == epochtime_name:       #epochtime 정해진 시간 형식으로 변환
                    i[j] = time.localtime(int(binascii.hexlify(i[j]),16))
                    i[j] = time.strftime(time_format, i[j])
                    ET = i[j]
                elif j== operator_name:       #OP 이름은 그대로 놔둠(ex: KASA)
                    i[j] = i[j].decode()
                    OP = i[j]
                elif j== embark_name:         #PI 이름은 입력된 딕셔너리에 정해진 형태로 변환(ex: 0114->LP)
                    i[j] = embark_dic[binascii.hexlify(i[j]).decode()]
                    PI = i[j]
                elif j == 'CRC_test':        #CRC test 결과: 1or0
                    i[j] = i[j]
                else:
                    i[j] = str(binascii.hexlify(i[j]).decode())
            writing_txt('./processed_data/',OP,PI,ET,i,str(count))

#데이터 처리 프로세스
class PDPS:
    def __init__(self, file_name): #file_name: 읽는 파일(경로 포함)
        
        #파일 열기
        with open(file_name, 'rb+') as f:
            full_data = f.read()

        self.embark_id = read_payload_id('payload_id') #pi읽기 함수
        
        self.data_list = [] #세트별 분할
        self.data_var_list = [] #세트별 분할된 변수 딕셔너리 data_var_list[n][name]: n번째 데이터 세트의 name변수
        
        remain_data = full_data
        done = False
        while not done:
            sliced_data,remain_data, PI, done = slicing_data(remain_data, self.embark_id)
            self.data_list.append(sliced_data) #데이터 세트 추가
            data_var_dic = dividing_dataset(sliced_data,PI)
            data_var_dic['CRC_test'] = test_CRC(sliced_data,data_var_dic['CRC'])
            self.data_var_list.append(data_var_dic) #변수별 데이터 세트 추가
        
        self.DP = data_processing(self.data_var_list)
        self.DP.transform(self.embark_id) #데이터 변환
        
    #lp.value(세트 번호,변수 이름), 원하는 세트의 변수 출력, 변수 이름이 'all'이면 전부 출력
    def value(self,set_number=0, var_name='OP'):
        if var_name == 'all':
            value = self.data_var_list[set_number]
        else:
            value = self.data_var_list[set_number][var_name]
        return value

if __name__ =="__main__":
    #파일경로,이름
    file_name = "./resnipe/SNIPE_FM_P1_LP_G10_0-4_20210111.dat"
    data = PDPS(file_name) #embark_id: 탑재체 이름 딕셔너리, file_name: 읽는 파일(경로 포함)

    print(data.value(0, 'ET')) #0번 세트의 ET변수 출력
    print(data.value(0, 'all')) #0번 세트 모든 변수 출력