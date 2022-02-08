import logging
import os

from selenium import webdriver
from msedge.selenium_tools import EdgeOptions, Edge
from html.parser import HTMLParser
from urllib import request
import re
import time
import subprocess
import threading
logger = logging.getLogger()
logger.setLevel(logging.INFO)
log_path = "./log.txt"
fh = logging.FileHandler(log_path,mode='w')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s")
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)
options = EdgeOptions()
options.use_chromium = True
options.add_argument("window-size=400,800")
options.add_argument("disable-extensions")
options.add_argument("disable-gpu")
options.add_argument("headless")
options.add_argument("disable-software-rasterizer")
options.add_argument("no-sandbox")
options.add_argument("blink-settings=imagesEnabled=false")
def _get_attr(attrs, attr_name):
    for attr in attrs:
        if attr[0] == attr_name:
            return attr[1]
    return None
def timeToSecond(time_str):
    #"00:12"
    if len(time_str.split(":"))==2:
        time_tmp = time.strptime(time_str,"%M:%S")
    else:
        time_tmp = time.strptime(time_str, "%H:%M:%S")
    return time_tmp.tm_sec + time_tmp.tm_min*60 + time_tmp.tm_hour*3600
class MyVideo(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.video_info = {
            "name":None,
            "url":None,
            "view":None,
            "msg":None,
            "time_now":0,
            "time_total":999999999
        }
        self.in_timenow = False
        self.in_timetotal = False
    def handle_starttag(self, tag, attrs):
        if tag=='span' and _get_attr(attrs,'class'):
            if 'video-time-now' in _get_attr(attrs,'class'):
                self.in_timenow = True
        if tag=='span' and _get_attr(attrs,'class'):
            if 'video-time-total' in _get_attr(attrs,'class'):
                self.in_timetotal = True
        if tag=='span' and _get_attr(attrs,'class')=='view':
            result = re.findall("总播放数(.+)",_get_attr(attrs,'title'))
            if result:
                view_count = int(result[0])
            else:
                view_count = 0
            self.video_info['view'] = view_count
            logger.debug("video view count:{}".format(view_count))
        if tag=='span' and _get_attr(attrs,'class')=='dm':
            result = re.findall("历史累计弹幕数(.+)",_get_attr(attrs,'title'))
            if result:
                view_count = int(result[0])
            else:
                view_count = 0
            self.video_info['msg'] = view_count
            logger.debug("video msg count:{}".format(view_count))
    def handle_data(self, data: str) -> None:
        if self.in_timenow:
            time_data = timeToSecond(data)
            self.video_info['time_now'] = time_data
            self.in_timenow = False
            logger.debug("video current time is {}".format(time_data))
        if self.in_timetotal:
            time_data = timeToSecond(data)
            if time_data == 0:
                pass
            else:
                self.video_info['time_total'] = time_data
            self.in_timetotal = False
            logger.debug("video total time is {}".format(time_data))
    def clear(self):
        self.video_info.clear()
class MyParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.video_list = []
        self.total_page = 1
        self.current_page = None
        self.multi_pages = False
        self.in_current = None
        self.in_a = None
    def handle_starttag(self, tag, attrs):
        if tag=='li' and (_get_attr(attrs,'class')=='small-item fakeDanmu-item' or
                          _get_attr(attrs,'class')=='small-item fakeDanmu-item new'):
            video_url = "https://bilibili.com/video/" + _get_attr(attrs,"data-aid")
            logger.info("add video url:{}".format(video_url))
            self.video_list.append(video_url)
        if tag=='ul' and _get_attr(attrs,'class')=='be-pager':
            logger.info("detected multiple pages for video")
            self.multi_pages = True
        if tag=='li' and self.multi_pages and _get_attr(attrs,'class')=='be-pager-item' and _get_attr(attrs,"title"):
            result = re.findall("最后一页:(.+)",_get_attr(attrs,"title"))
            if result:
                logger.info("detected video pages {}".format(int(result[0])))
                self.total_page = int(result[0])
        if tag=='li' and self.multi_pages and _get_attr(attrs,'class')=='be-pager-item be-pager-item-active':
            self.in_current = True
            # current_page = _get_attr(attrs,"title")
            # self.current_page = int(current_page)
        if tag=='a' and self.in_current:
            self.in_a = True
    def handle_data(self, data: str) -> None:
        if self.in_a:
            self.current_page = int(data)
            logger.info("detected video current page {}".format(data))
    def handle_endtag(self, tag: str) -> None:
        if self.in_a:
            self.in_a = False
        if tag=='li' and self.in_current:
            self.in_current = False
    def clear(self):
        self.video_list.clear()
        self.multi_pages = False
class MyThread(threading.Thread):
    def __init__(self,url,view_time=5,interval=305,time_limit=60):
        self.url = url
        self.view_time = view_time
        self.interval = interval
        self.start_time = time.time()
        self.time_limit = time_limit
        self.browser = None
        threading.Thread.__init__(self)
    def run(self):
        while(1):
            try:
                self.runSub()
            except:
                logger.info("process :{} failed,restart".format(self.url))
                if self.browser:
                    self.browser.quit()
                self.start_time = time.time()
    def runSub(self):
        self.browser = Edge(executable_path="msedgedriver.exe",options=options)
        self.browser.get(self.url)
        logger.info("open video url:{}".format(self.url))
        current_time = self.start_time
        view_num = None
        cnt = 0
        while((current_time-self.start_time)<self.time_limit):
            page_source = self.browser.page_source
            tmp = MyVideo()
            tmp.feed(page_source)
            if not view_num:
                view_num = tmp.video_info['view']
                print("view_num:{} cnt:{}".format(view_num,cnt))
                if cnt>3:
                    cnt = 0
                    print("refresh")
                    self.browser.refresh()
            time_now = tmp.video_info['time_now']
            time_total = tmp.video_info['time_total']
            time_max = min(time_total,self.view_time)
            if time_now >= time_max:
                logger.info("{} view num:{}".format(self.url,view_num))
                break
            time.sleep(2)
            current_time = time.time()
            cnt += 1
        self.browser.quit()
        time.sleep(self.interval)
        self.start_time = time.time()


class MyScript():
    def __init__(self,user_id,interval=300,max_page=5):
        self.user_id = user_id
        self.interval = interval
        self.video_list = []
        self.total_page = None
        self.current_page = 1
        self.multi_pages = False
        self.max_page = max_page
        self.video_url = "https://space.bilibili.com/{}/video".format(user_id)
    def getVideo(self):
        self.browser = Edge(executable_path="msedgedriver.exe",options=options)
        self.browser.get(self.video_url)
        page_source = self.browser.page_source
        tmp = MyParser()
        tmp.feed(page_source)
        self.total_page = tmp.total_page
        self.current_page = tmp.current_page
        self.video_list.extend(tmp.video_list)
        max_page = min(self.total_page,self.max_page)
        for i in range(self.current_page+1,max_page+1):
            self._selectPage(i)
            tmp.clear()
            page_source = self.browser.page_source
            tmp.feed(page_source)
            self.video_list.extend(tmp.video_list)
        self.browser.quit()
    def _selectPage(self,num,sleep=5):
        success = False
        pages = self.browser.find_elements_by_class_name("be-pager-item")
        for page in pages:
            if page.text==str(num):
                success = True
                break
        if not success:
            raise Exception("unexpected error page not currect total:{} now select:{}".format(self.total_page,num))
        page.click()
        time.sleep(sleep)
    def openUrl(self):
        interval = 150
        # num = len(self.video_list)
        # per_s = 1
        # total = interval * per_s
        # if num >= total:
        #     per_s = int(num/interval) if num%interval==0 else int(num/interval)+1
        for index,i in enumerate(self.video_list):
        #     if (index+1)%per_s==0:
        #         time.sleep(1)
            tmp_thread = MyThread(i,interval=interval)
            tmp_thread.start()
            time.sleep(3)
import subprocess,datetime,pickle
from pynput.keyboard import Key, Controller
class MyUpload():
    def __init__(self,url,source_file,time_len,file_path="cookies"):
        self.url = url
        self.source_file = source_file
        self.time_len = time_len
        self.file_path = file_path
    def cutVideo(self,source_file):
        result = subprocess.Popen("ffmpeg.exe -i {} 2>&1".format(source_file), stdout=subprocess.PIPE, shell=True)
        out, err = result.communicate()
        status = result.wait()
        time_result = re.findall("Duration: (.+?), ", out.decode())
        if time_result:
            video_len = timeToSecond(time_result[0].split(".")[0])
        else:
            raise Exception
        time_len = self.time_len
        num = int(video_len / time_len)
        tmp_time = datetime.datetime(2000, 1, 1, 0, 0, 0)
        os.makedirs("videos", exist_ok=True)
        for i in range(num):
            output_file = os.path.join("videos", "video{}.mp4".format(i))
            time_str = tmp_time.strftime("%H:%M:%S")
            cut_cmd = "ffmpeg.exe -ss {} -t {} -i {} {}".format(time_str, time_len, source_file, output_file)
            result = subprocess.Popen(cut_cmd, stdout=subprocess.PIPE, shell=True)
            out, err = result.communicate()
            status = result.wait()
            tmp_time += datetime.timedelta(0, time_len)
    def saveCookies(self):
        browser = Edge(executable_path="msedgedriver.exe", options=options)
        browser.get(self.url)
        input("input anything to continue")
        cookie = browser.get_cookies()
        browser.quit()
        file_tmp = open(self.file_path,'wb')
        pickle.dump(cookie,file_tmp)
        logger.info("cookies saved to {}".format(self.file_path))
    def loadCookies(self):
        with open(self.file_path, 'rb') as f:
            cookies = pickle.load(f)
        return cookies
    @staticmethod
    def _uploadFile(file_upload):
        time.sleep(8)
        keyboard = Controller()
        keyboard.press(Key.shift)
        keyboard.release(Key.shift)
        keyboard.type(file_upload)
        time.sleep(5)
        keyboard.press(Key.enter)
        keyboard.release(Key.enter)
        time.sleep(4)
    def uploadVideos(self):
        file_path = getCutVideo("D:\\pycharm\\untitled\\videos")
        url = "https://member.bilibili.com/platform/upload/video/frame"
        browser = Edge(executable_path="msedgedriver.exe", options=options)
        browser.get(self.url)
        cookies = self.loadCookies()
        for cookie in cookies:
            browser.add_cookie(cookie)
        browser.get(self.url)
        time.sleep(2)
        jump = browser.find_elements_by_class_name("jump")
        if jump:
            for i in jump:
                try:
                    i.click()
                    time.sleep(6)
                except:
                    pass
        browser.switch_to_frame("videoUpload")
        for i in file_path:
            self.uploadVideo(i,browser)
    def uploadVideo(self,file_upload,browser):
        for k in range(10):
            upload = browser.find_elements_by_class_name("upload-btn")
            if upload:
                upload[0].click()
                break
            else:
                time.sleep(1)
        self._uploadFile(file_upload)
        upload = browser.find_elements_by_class_name("upload-btn")
        while(1):
            if not upload:
                break
            if upload and ("上传视频" in upload[0].text):
                logger.info("not uploading try again")
                upload[0].click()
                self._uploadFile(file_upload)
            upload = browser.find_elements_by_class_name("upload-btn")
        for k in range(50):
            success = browser.find_elements_by_class_name("success")
            if success:
                if success[0].text == "上传完成":
                    tag_more = browser.find_elements_by_class_name("tag-more")
                    if not tag_more:
                        raise Exception("cannot find tag_more button")
                    tag_more[0].click()
                    time.sleep(1)
                    logger.info("uploading finished")
                    break
            logger.info("wait uploading")
            time.sleep(2)
        if k == 49:
            raise Exception("failed")
        for k in range(10):
            event_input = browser.find_elements_by_class_name("dialog-item")
            if not event_input:
                time.sleep(1)
                continue
            for i in event_input:
                if "幻塔UP主激励计划" in i.text:
                    i.click()
                    time.sleep(1)
                    button = browser.find_elements_by_class_name("bcc-button.submit-add.bcc-button--primary.large")
                    if not button:
                        raise Exception("cannot find confirm button")
                    button[0].click()
                    time.sleep(1)
                    logger.info("confirm event")
                    break
        confirm = browser.find_elements_by_class_name("submit-add")
        if not confirm:
            raise Exception("cannot find upload button")
        confirm[0].click()
        flag = False
        for k in range(10):
            upload_again = browser.find_elements_by_class_name("bcc-button.bcc-button--default.max-large")
            for i in upload_again:
                if i.text == "再投一个":
                    i.click()
                    time.sleep(2)
                    logger.info("{} confirm upload".format(file_upload))
                    flag = True
                    break
            if flag:
                break
            time.sleep(1)
        pass
def getCutVideo(path):
    file_list = os.listdir(path)
    file_path = []
    for i in file_list:
        file_path.append(os.path.join(path,i))
    return file_path

# tmp_class = MyUpload("https://member.bilibili.com/platform/upload/video/frame","video.mp4",10)
# tmp_class.uploadVideos()
# from moviepy.video.io.VideoFileClip import VideoFileClip
# video = VideoFileClip("video.mp4")
# video.subclip(10,20)
# video.to_videofile("video1.mp4")
tmp_class = MyScript("")
tmp_class.getVideo()
tmp_class.openUrl()
ua_headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36'}
# url = "https://space.bilibili.com/9824766/video"
# url = "http://httpbin.org/ip"
# options.add_argument("user-agent='Mozilla/5.0 (iPod; U; CPU iPhone OS 2_1 like Mac OS X; ja-jp) AppleWebKit/525.18.1 (KHTML, like Gecko) Version/3.1.1 Mobile/5F137 Safari/525.20'")
# browser = Edge(executable_path="msedgedriver.exe", options=options)
# browser.get(url)
# page_source = browser.page_source
# tmp = MyParser()
# tmp.feed(page_source)
# agent = browser.execute_script("return navigator.userAgent")
# print(agent)




# tmp = MyParser()
# tmp.feed(page_source)
# tmp_request = request.Request(url)
# result = request.urlopen(tmp_request).read()
#
# tmp_html = open("./tmp.html","wb")
# tmp_html.write(result)
# tmp_html.close()
