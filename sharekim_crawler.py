import os, sys
import pymysql
from time import sleep
from multiprocessing import Pool
from traceback import print_exc

from sharekim_util import *

from selenium import webdriver
from selenium.common.exceptions import *
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class Crawler:
    def __init__(self):
        self.house_list = []

    def crawl(self, urls: list) -> list:
        driver = get_driver(visible=False)
        address_driver = get_driver(visible=False)

        for url in urls:
            if url == "https://sharekim.com/":
                continue
            try:
                driver.get(url)
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "root"))
                )

                # 매물명
                house_info = driver.find_element_by_xpath(
                    """//*[@id="blur-wrap"]/div[3]/div[1]/div[2]/div/div[1]/div[2]/div/div[2]""")
                house_info_data = house_info.text.strip()
                loc = house_info_data.find(":")
                house_name = house_info_data[loc + 2:].replace(",", "").replace("\n", "")

                detail_info = driver.find_element_by_xpath(
                    """//*[@id="blur-wrap"]/div[3]/div[1]/div[1]/div[2]/section""")
                detail_info_data = detail_info.text.strip()

                # 건물형태
                if detail_info_data.find("빌라") >= 0:
                    house_type = "villa"
                elif detail_info_data.find("아파트") >= 0:
                    house_type = "apt"
                elif detail_info_data.find("단독주택") >= 0:
                    house_type = "house"
                elif detail_info_data.find("원룸") >= 0:
                    house_type = "oneroom"
                elif detail_info_data.find("오피스텔") >= 0:
                    house_type = "office"
                else:
                    house_type = "etc"

                # 방
                if detail_info_data.find("방") >= 0:
                    total_room_info = driver.find_element_by_xpath(
                        """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[1]/h5[2]""")
                    total_room = total_room_info.text.strip()
                    loc1 = total_room.find("(")
                    loc2 = total_room.find(")")
                    room_cnt = int(total_room[loc1:loc2].replace("(", "").replace(")", "").replace(" ", ""))
                else:
                    room_cnt = None
                # 화장실
                if detail_info_data.find("화장실") >= 0:
                    loc = detail_info_data.find("화장실")
                    try:
                        washroom_cnt = int(detail_info_data[loc + 3:loc + 5].replace("\n", "").replace(" ", ""))
                    except ValueError:
                        washroom_cnt = None
                else:
                    washroom_cnt = None
                # 층
                if detail_info_data.find("총층") >= 0:
                    loc = detail_info_data.find("총층")
                    now_floor = detail_info_data[loc + 2:loc + 5].replace("\n", "").replace(" ", "")
                    if now_floor.find("지하") >= 0:
                        now_floor = None
                    else:
                        now_floor = int(now_floor.replace("층", "").replace(" ", ""))
                else:
                    now_floor = None
                # 총층
                if detail_info_data.find("층/총층") >= 0:
                    loc = detail_info_data.find("층/총층")
                    total_floor = detail_info_data[loc + 7:loc + 10].replace("\n", "").replace("/", "")
                    total_floor = int(total_floor.replace("층", ""))
                else:
                    total_floor = None
                # 전체면적
                if detail_info_data.find("㎡") >= 0:
                    loc1 = detail_info_data.find("적")
                    loc2 = detail_info_data.find("㎡")
                    house_area = float(detail_info_data[loc1 + 1:loc2].replace("\n", "").replace(" ", ""))
                else:
                    house_area = None

                # 도로명 주소
                address = driver.find_element_by_xpath(
                    """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[2]/p""")
                road_address = address.text.strip()
                if road_address.find("경기") >= 0 or road_address.find("인천") >= 0:
                    district = None
                    building = None
                else:
                    (district, building) = self.address_trans(address_driver, road_address)

                room_dict_list = []

                j = 3
                for i in range(0, room_cnt):
                    unit_room = driver.find_element_by_xpath(
                        """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[1]/div[""" + str(j) + """]""")
                    unit_room_data = unit_room.text.strip()

                    bed_dict_list = []

                    # 성별전용
                    if unit_room_data.find("여성") >= 0:
                        gender = "F"
                    elif unit_room_data.find("남성") >= 0:
                        gender = "M"
                    elif unit_room_data.find("무관") >= 0:
                        gender = "N"
                    else:
                        gender = None

                    # 면적
                    if unit_room_data.find("㎡") >= 0:
                        unit_loc1 = unit_room_data.find("(")
                        unit_loc2 = unit_room_data.find("㎡")
                        room_area = unit_room_data[unit_loc1 + 1:unit_loc2].replace("\n,", "")
                        if room_area.find(")") >= 0:
                            unit_loc3 = room_area.find(")")
                            room_area = room_area[unit_loc3 + 1:unit_loc2].replace("\n", "").replace("(", "")
                        room_area = float(room_area.replace(" ", ""))
                    else:
                        room_area = None

                    # 인실
                    unit_loc3 = unit_room_data.find("실")
                    bed_cnt = int(unit_room_data[unit_loc3 - 2:unit_loc3 - 1].replace("\n", "").replace(" ", ""))

                    # 방 이름
                    room_section_elem = driver.find_element_by_xpath(
                        """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[1]""")
                    unit_select_items_elem = room_section_elem.find_elements_by_class_name("UnitSelctItem")
                    room_name = unit_select_items_elem[i].find_elements_by_tag_name("span")[0].text

                    bed_label_elems = unit_select_items_elem[i].find_elements_by_tag_name("label")

                    # 각 침대 만실, 보증금, 월세
                    for bed in bed_label_elems:
                        badge_span_elem = bed.find_elements_by_tag_name('span')[1]

                        # div 예외처리
                        if badge_span_elem.text == "상세설명":
                            badge_span_elem = bed.find_elements_by_tag_name('span')[4]
                            # 만실
                            if badge_span_elem.text == "만실":
                                is_full = True
                            else:
                                is_full = False

                            rent_fee_elem = bed.find_elements_by_tag_name('span')[6]
                            rent_fee = str(rent_fee_elem.text)[:str(rent_fee_elem.text).find('만원')].split('/')
                            # 보증금
                            deposit = rent_fee[0].strip()
                            # 월세
                            monthly_rent = rent_fee[1].strip()

                        else:
                            # 만실
                            if badge_span_elem.text == "만실":
                                is_full = True
                            else:
                                is_full = False

                            rentfee_elem = bed.find_elements_by_tag_name('span')[3]
                            rent_fee = str(rentfee_elem.text)[:str(rentfee_elem.text).find('만원')].split('/')
                            # 보증금
                            deposit = rent_fee[0].strip()
                            # 월세
                            monthly_rent = rent_fee[1].strip()

                        bed_data_dict = {"is_full": is_full, "deposit": deposit, "monthly_rent": monthly_rent,
                                         "house_name": house_name, "room_name": room_name}
                        bed_dict_list.append(bed_data_dict)

                    j += 1
                    room_data_dict = {"room_name": room_name, "gender": gender, "bed_cnt": bed_cnt,
                                      "room_area": room_area,
                                      "bed_dict_list": bed_dict_list}
                    room_dict_list.append(room_data_dict)

                house_data_dict = {"house_name": house_name, "house_area": house_area, "house_type": house_type,
                                   "room_cnt": room_cnt, "washroom_cnt": washroom_cnt, "now_floor": now_floor,
                                   "total_floor": total_floor, "road_address": road_address, "district": district,
                                   "building": building, "room_dict_list": room_dict_list}
                self.house_list.append(house_data_dict)
            except Exception as e:
                _, _, tb = sys.exc_info()
                print('error line No = {}'.format(tb.tb_lineno))
                print(e)
                print(url)
                continue

        driver.quit()
        address_driver.quit()

    def address_trans(self, driver: webdriver, road_address: str) -> tuple:
        district = None
        building = None

        try:
            driver.get("http://www.juso.go.kr/support/AddressMainSearch.do?searchType=TOTAL")

            driver.find_element_by_xpath("""//*[@id="keyword"]""").clear()
            driver.find_element_by_xpath("""//*[@id="keyword"]""").send_keys(road_address)
            sleep(0.1)
            driver.find_element_by_xpath("""//*[@id="searchButton"]""").click()

        except:
            return district, building

        try:
            building_info = driver.find_element_by_xpath("""//*[@id="list1"]/div[2]/span[2]""")
            building_data = building_info.text.strip()

            # 구로구일 경우
            if building_data.find("구로구") >= 0:
                district = "구로구"
                building = "구로동"
            # 구 찾으면
            elif building_data.find("구") >= 0:
                loc1 = building_data.find("구")
                district = building_data[loc1 - 3:loc1 + 1].replace("시", "").replace("별", "").replace(" ", "")
                # 동
                if building_data.find("동") >= 0:
                    building = building_data[loc1 + 2:loc1 + 6].strip()
                    building = "".join([i for i in building if not i.isdigit()])
                    # 필동가 -> 필동
                    if building == "필동가":
                        building = "필동"
                else:
                    building = None
            # 구 못 찾을 경우
            else:
                district = None
                building = None

        except NoSuchElementException:
            loc1 = road_address.find("구")
            district = road_address[loc1 - 3:loc1 + 1].replace("시", "").replace("별", "").replace(" ", "")
            loc2 = road_address.find("동")
            building = building_data[loc2 - 3:loc2 + 1].strip()
            building = "".join([i for i in building if not i.isdigit()])

        finally:
            return district, building

    @timer
    def run(self) -> list:
        retry_cnt = 3
        while True:
            try:
                driver = get_driver(visible=False)
                driver.get("https://sharekim.com/search?location=37.60747912093436,126.9543820360534,9&category=[1]")
                house_url_list = get_house_list_urls(driver)
            except:
                retry_cnt -= 1
                print("재시도 횟수: {}".format(4-retry_cnt))
                if retry_cnt == 0:
                    raise
            else:
                if len(house_url_list)<100:
                    continue
                print("성공")
                print("링크 갯수 {}개".format(len(house_url_list)))
                break

        self.crawl(house_url_list)
        return self.house_list


class Crawler_stopped:
    def __init__(self, visible=False):
        self.visible = visible
        self.house_list = []
        self.driver = get_driver(self.visible)
        self.add_driver = get_driver(self.visible)

    # url을 입력받아 각 sharekim detail page의 house, room, bed 정보를 저장한 dict를 반환
    def crawl(self, url: str) -> dict:
        if isinstance(url, str):
            try:
                driver.get(url)

                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "root"))
                )

                # 매물명
                house_info = driver.find_element_by_xpath(
                    """//*[@id="blur-wrap"]/div[3]/div[1]/div[2]/div/div[1]/div[2]/div/div[2]""")
                house_info_data = house_info.text.strip()
                loc = house_info_data.find(":")
                house_name = house_info_data[loc + 2:].replace(",", "").replace("\n", "")

                detail_info = driver.find_element_by_xpath(
                    """//*[@id="blur-wrap"]/div[3]/div[1]/div[1]/div[2]/section""")
                detail_info_data = detail_info.text.strip()

                # 건물형태
                if detail_info_data.find("빌라") >= 0:
                    house_type = "villa"
                elif detail_info_data.find("아파트") >= 0:
                    house_type = "apt"
                elif detail_info_data.find("단독주택") >= 0:
                    house_type = "house"
                elif detail_info_data.find("원룸") >= 0:
                    house_type = "oneroom"
                elif detail_info_data.find("오피스텔") >= 0:
                    house_type = "office"
                elif detail_info_data.find("기타") >= 0:
                    house_type = "etc"
                else:
                    house_type = None

                # 방
                if detail_info_data.find("방") >= 0:
                    total_room_info = driver.find_element_by_xpath(
                        """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[1]/h5[2]""")
                    total_room = total_room_info.text.strip()
                    loc1 = total_room.find("(")
                    loc2 = total_room.find(")")
                    room_cnt = int(total_room[loc1:loc2].replace("(", "").replace(")", "").replace(" ", ""))
                else:
                    room_cnt = None
                # 화장실
                if detail_info_data.find("화장실") >= 0:
                    loc = detail_info_data.find("화장실")
                    try:
                        washroom_cnt = int(detail_info_data[loc + 3:loc + 5].replace("\n", "").replace(" ", ""))
                    except ValueError:
                        washroom_cnt = None
                else:
                    washroom_cnt = None
                # 층
                if detail_info_data.find("총층") >= 0:
                    loc = detail_info_data.find("총층")
                    now_floor = detail_info_data[loc + 2:loc + 5].replace("\n", "").replace(" ", "")
                    if now_floor.find("지하") >= 0:
                        now_floor = None
                    else:
                        now_floor = int(now_floor.replace("층", "").replace(" ", ""))
                else:
                    now_floor = None
                # 총층
                if detail_info_data.find("층/총층") >= 0:
                    loc = detail_info_data.find("층/총층")
                    total_floor = detail_info_data[loc + 7:loc + 10].replace("\n", "").replace("/", "")
                    total_floor = int(total_floor.replace("층", ""))
                else:
                    total_floor = None
                # 전체면적
                if detail_info_data.find("㎡") >= 0:
                    loc1 = detail_info_data.find("적")
                    loc2 = detail_info_data.find("㎡")
                    house_area = float(detail_info_data[loc1 + 1:loc2].replace("\n", "").replace(" ", ""))
                else:
                    house_area = None

                # 도로명 주소
                address = driver.find_element_by_xpath(
                    """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[2]/p""")
                road_address = address.text.strip()
                if road_address.find("경기") >= 0 or road_address.find("인천") >= 0:
                    district = None
                    building = None
                else:
                    (district, building) = address_trans(address_driver, road_address)

                room_dict_list = []

                j = 3
                for i in range(0, room_cnt):
                    unit_room = driver.find_element_by_xpath(
                        """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[1]/div[""" + str(j) + """]""")
                    unit_room_data = unit_room.text.strip()

                    bed_dict_list = []

                    # 성별전용
                    if unit_room_data.find("여성") >= 0:
                        gender = "F"
                    elif unit_room_data.find("남성") >= 0:
                        gender = "M"
                    elif unit_room_data.find("무관") >= 0:
                        gender = "N"
                    else:
                        gender = None

                    # 면적
                    if unit_room_data.find("㎡") >= 0:
                        unit_loc1 = unit_room_data.find("(")
                        unit_loc2 = unit_room_data.find("㎡")
                        room_area = unit_room_data[unit_loc1 + 1:unit_loc2].replace("\n,", "")
                        if room_area.find(")") >= 0:
                            unit_loc3 = room_area.find(")")
                            room_area = room_area[unit_loc3 + 1:unit_loc2].replace("\n", "").replace("(", "")
                        room_area = float(room_area.replace(" ", ""))
                    else:
                        room_area = None

                    # 인실
                    unit_loc3 = unit_room_data.find("실")
                    bed_cnt = int(unit_room_data[unit_loc3 - 2:unit_loc3 - 1].replace("\n", "").replace(" ", ""))

                    # 방 이름
                    room_section_elem = driver.find_element_by_xpath(
                        """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[1]""")
                    unit_select_items_elem = room_section_elem.find_elements_by_class_name("UnitSelctItem")
                    room_name = unit_select_items_elem[i].find_elements_by_tag_name("span")[0].text

                    bed_label_elems = unit_select_items_elem[i].find_elements_by_tag_name("label")

                    # 각 침대 만실, 보증금, 월세
                    for bed in bed_label_elems:
                        badge_span_elem = bed.find_elements_by_tag_name('span')[1]

                        # div 예외처리
                        if badge_span_elem.text == "상세설명":
                            badge_span_elem = bed.find_elements_by_tag_name('span')[4]
                            # 만실
                            if badge_span_elem.text == "만실":
                                is_full = True
                            else:
                                is_full = False

                            rent_fee_elem = bed.find_elements_by_tag_name('span')[6]
                            rent_fee = str(rent_fee_elem.text)[:str(rent_fee_elem.text).find('만원')].split('/')
                            # 보증금
                            deposit = rent_fee[0].strip()
                            # 월세
                            monthly_rent = rent_fee[1].strip()

                        else:
                            # 만실
                            if badge_span_elem.text == "만실":
                                is_full = True
                            else:
                                is_full = False

                            rentfee_elem = bed.find_elements_by_tag_name('span')[3]
                            rent_fee = str(rentfee_elem.text)[:str(rentfee_elem.text).find('만원')].split('/')
                            # 보증금
                            deposit = rent_fee[0].strip()
                            # 월세
                            monthly_rent = rent_fee[1].strip()

                        bed_data_dict = {"is_full": is_full, "deposit": deposit, "monthly_rent": monthly_rent,
                                         "house_name": house_name, "room_name": room_name}
                        bed_dict_list.append(bed_data_dict)

                    j += 1
                    room_data_dict = {"room_name": room_name, "gender": gender, "bed_cnt": bed_cnt,
                                      "room_area": room_area,
                                      "bed_data_list": bed_dict_list}
                    room_dict_list.append(room_data_dict)

                house_data_dict = {"house_name": house_name, "house_area": house_area, "house_type": house_type,
                                   "room_cnt": room_cnt, "washroom_cnt": washroom_cnt, "now_floor": now_floor,
                                   "total_floor": total_floor, "road_address": road_address, "district": district,
                                   "building": building, "room_dict_list": room_dict_list}
            except Exception as e:
                raise
            finally:
                self.driver.quit()
                self.add_driver.quit()
            return house_data_dict

        elif isinstance(url, list):
            house_data_dict_list = []
            try:
                for page in url:
                    detail_driver = get_driver(self.visible)
                    address_driver = get_driver(self.visible)
                    detail_driver.get(page)

                    WebDriverWait(detail_driver, 5).until(
                        EC.presence_of_element_located((By.ID, "root"))
                    )

                    # 매물명
                    house_info = detail_driver.find_element_by_xpath(
                        """//*[@id="blur-wrap"]/div[3]/div[1]/div[2]/div/div[1]/div[2]/div/div[2]""")
                    house_info_data = house_info.text.strip()
                    loc = house_info_data.find(":")
                    house_name = house_info_data[loc + 2:].replace(",", "").replace("\n", "")

                    detail_info = detail_driver.find_element_by_xpath(
                        """//*[@id="blur-wrap"]/div[3]/div[1]/div[1]/div[2]/section""")
                    detail_info_data = detail_info.text.strip()

                    # 건물형태
                    if detail_info_data.find("빌라") >= 0:
                        house_type = "villa"
                    elif detail_info_data.find("아파트") >= 0:
                        house_type = "apt"
                    elif detail_info_data.find("단독주택") >= 0:
                        house_type = "house"
                    elif detail_info_data.find("원룸") >= 0:
                        house_type = "oneroom"
                    elif detail_info_data.find("오피스텔") >= 0:
                        house_type = "office"
                    elif detail_info_data.find("기타") >= 0:
                        house_type = "etc"
                    else:
                        house_type = None

                    # 방
                    if detail_info_data.find("방") >= 0:
                        total_room_info = detail_driver.find_element_by_xpath(
                            """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[1]/h5[2]""")
                        total_room = total_room_info.text.strip()
                        loc1 = total_room.find("(")
                        loc2 = total_room.find(")")
                        room_cnt = int(total_room[loc1:loc2].replace("(", "").replace(")", "").replace(" ", ""))
                    else:
                        room_cnt = None
                    # 화장실
                    if detail_info_data.find("화장실") >= 0:
                        loc = detail_info_data.find("화장실")
                        try:
                            washroom_cnt = int(detail_info_data[loc + 3:loc + 5].replace("\n", "").replace(" ", ""))
                        except ValueError:
                            washroom_cnt = None
                    else:
                        washroom_cnt = None
                    # 층
                    if detail_info_data.find("총층") >= 0:
                        loc = detail_info_data.find("총층")
                        now_floor = detail_info_data[loc + 2:loc + 5].replace("\n", "").replace(" ", "")
                        if now_floor.find("지하") >= 0:
                            now_floor = None
                        else:
                            now_floor = int(now_floor.replace("층", "").replace(" ", ""))
                    else:
                        now_floor = None
                    # 총층
                    if detail_info_data.find("층/총층") >= 0:
                        loc = detail_info_data.find("층/총층")
                        total_floor = detail_info_data[loc + 7:loc + 10].replace("\n", "").replace("/", "")
                        total_floor = int(total_floor.replace("층", ""))
                    else:
                        total_floor = None
                    # 전체면적
                    if detail_info_data.find("㎡") >= 0:
                        loc1 = detail_info_data.find("적")
                        loc2 = detail_info_data.find("㎡")
                        house_area = float(detail_info_data[loc1 + 1:loc2].replace("\n", "").replace(" ", ""))
                    else:
                        house_area = None

                    # 도로명 주소
                    address = detail_driver.find_element_by_xpath(
                        """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[2]/p""")
                    road_address = address.text.strip()
                    if road_address.find("경기") >= 0 or road_address.find("인천") >= 0:
                        district = None
                        building = None
                    else:
                        (district, building) = self.address_trans(address_driver, road_address)

                    room_dict_list = []

                    j = 3
                    for i in range(0, room_cnt):
                        unit_room = detail_driver.find_element_by_xpath(
                            """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[1]/div[""" + str(j) + """]""")
                        unit_room_data = unit_room.text.strip()

                        bed_dict_list = []

                        # 성별전용
                        if unit_room_data.find("여성") >= 0:
                            gender = "F"
                        elif unit_room_data.find("남성") >= 0:
                            gender = "M"
                        elif unit_room_data.find("무관") >= 0:
                            gender = "N"
                        else:
                            gender = None

                        # 면적
                        if unit_room_data.find("㎡") >= 0:
                            unit_loc1 = unit_room_data.find("(")
                            unit_loc2 = unit_room_data.find("㎡")
                            room_area = unit_room_data[unit_loc1 + 1:unit_loc2].replace("\n,", "")
                            if room_area.find(")") >= 0:
                                unit_loc3 = room_area.find(")")
                                room_area = room_area[unit_loc3 + 1:unit_loc2].replace("\n", "").replace("(", "")
                            room_area = float(room_area.replace(" ", ""))
                        else:
                            room_area = None

                        # 인실
                        unit_loc3 = unit_room_data.find("실")
                        bed_cnt = int(unit_room_data[unit_loc3 - 2:unit_loc3 - 1].replace("\n", "").replace(" ", ""))

                        # 방 이름
                        room_section_elem = detail_driver.find_element_by_xpath(
                            """//*[@id="blur-wrap"]/div[3]/div[2]/div[1]/section[1]""")
                        unit_select_items_elem = room_section_elem.find_elements_by_class_name("UnitSelctItem")
                        room_name = unit_select_items_elem[i].find_elements_by_tag_name("span")[0].text

                        bed_label_elems = unit_select_items_elem[i].find_elements_by_tag_name("label")

                        # 각 침대 만실, 보증금, 월세
                        for bed in bed_label_elems:
                            badge_span_elem = bed.find_elements_by_tag_name('span')[1]

                            # div 예외처리
                            if badge_span_elem.text == "상세설명":
                                badge_span_elem = bed.find_elements_by_tag_name('span')[4]
                                # 만실
                                if badge_span_elem.text == "만실":
                                    is_full = True
                                else:
                                    is_full = False

                                rent_fee_elem = bed.find_elements_by_tag_name('span')[6]
                                rent_fee = str(rent_fee_elem.text)[:str(rent_fee_elem.text).find('만원')].split('/')
                                # 보증금
                                deposit = rent_fee[0].strip()
                                # 월세
                                monthly_rent = rent_fee[1].strip()

                            else:
                                # 만실
                                if badge_span_elem.text == "만실":
                                    is_full = True
                                else:
                                    is_full = False

                                rentfee_elem = bed.find_elements_by_tag_name('span')[3]
                                rent_fee = str(rentfee_elem.text)[:str(rentfee_elem.text).find('만원')].split('/')
                                # 보증금
                                deposit = rent_fee[0].strip()
                                # 월세
                                monthly_rent = rent_fee[1].strip()

                            bed_data_dict = {"is_full": is_full, "deposit": deposit, "monthly_rent": monthly_rent,
                                             "house_name": house_name, "room_name": room_name}
                            bed_dict_list.append(bed_data_dict)

                        j += 1
                        room_data_dict = {"room_name": room_name, "gender": gender, "bed_cnt": bed_cnt,
                                          "room_area": room_area,
                                          "bed_dict_list": bed_dict_list}
                        room_dict_list.append(room_data_dict)

                    house_data_dict = {"house_name": house_name, "house_area": house_area, "house_type": house_type,
                                       "room_cnt": room_cnt, "washroom_cnt": washroom_cnt, "now_floor": now_floor,
                                       "total_floor": total_floor, "road_address": road_address, "district": district,
                                       "building": building, "room_dict_list": room_dict_list}
                    house_data_dict_list.append(house_data_dict)
            except Exception as e:
                raise e
            finally:
                detail_driver.quit()
                address_driver.quit()
            return house_data_dict_list

    # crawl중 가져온 도로명주소 str을 구, 동 주소로 분리하여 반환
    def address_trans(self, driver: webdriver, road_address: str) -> tuple:
        district = None
        building = None

        try:
            driver.get("http://www.juso.go.kr/support/AddressMainSearch.do?searchType=TOTAL")

            driver.find_element_by_xpath("""//*[@id="keyword"]""").clear()
            driver.find_element_by_xpath("""//*[@id="keyword"]""").send_keys(road_address)
            sleep(0.1)
            driver.find_element_by_xpath("""//*[@id="searchButton"]""").click()

        except:
            return district, building

        try:
            building_info = driver.find_element_by_xpath("""//*[@id="list1"]/div[2]/span[2]""")
            building_data = building_info.text.strip()

            # 구로구일 경우
            if building_data.find("구로구") >= 0:
                district = "구로구"
                building = "구로동"
            # 구 찾으면
            elif building_data.find("구") >= 0:
                loc1 = building_data.find("구")
                district = building_data[loc1 - 3:loc1 + 1].replace("시", "").replace("별", "").replace(" ", "")
                # 동
                if building_data.find("동") >= 0:
                    building = building_data[loc1 + 2:loc1 + 6].strip()
                    building = "".join([i for i in building if not i.isdigit()])
                    # 필동가 -> 필동
                    if building == "필동가":
                        building = "필동"
                else:
                    building = None
            # 구 못 찾을 경우
            else:
                district = None
                building = None

        except NoSuchElementException:
            loc1 = road_address.find("구")
            district = road_address[loc1 - 3:loc1 + 1].replace("시", "").replace("별", "").replace(" ", "")
            loc2 = road_address.find("동")
            building = building_data[loc2 - 3:loc2 + 1].strip()
            building = "".join([i for i in building if not i.isdigit()])

        finally:
            return district, building

    @timer
    def run(self, house_url_list: list, worker=1) -> list:
        # detail url수집
        try:
            if worker == 1:
                for house_url in house_url_list:
                    self.house_list.append(self.crawl(house_url))
            else:
                divided_url_list = list(list_divider(house_url_list, worker))
                pool = Pool(processes=worker)
                res = pool.map(self.crawl, divided_url_list)
                result = [x for y in res for x in y]
                self.house_list = result

        except Exception as e:
            print(e)
            print_exc()
            raise e

        return self.house_list
