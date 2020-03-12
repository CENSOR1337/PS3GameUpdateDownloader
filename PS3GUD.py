#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# PS3GameUpdateDownloader by shinrax2

#built-in
import urllib.request
import ssl
import xml.etree.ElementTree as ET
import os
import hashlib
import sys
import shutil
import json

#pip packages
import requests

#local files
import utils

class PS3GUD():
    def __init__(self, window=None):
        if window != None:
            self.logger = utils.Logger("log.txt", window)
        else:
            self.logger = utils.Logger("log.txt")
        self.loc = DummyLoc()
        self.configFile = "./config.json"
        self.config = {}
        self.Updates = {}
        self.DlList = []
        self.titleid = ""
    
    def setWindow(self, window):
        self.logger = utils.Logger("log.txt", window)
        
    def setLoc(self, loc):
        self.loc = loc

    def logHeader(self):
        self.logger.log("PS3GameUpdateDownloader")
        self.logger.log("Config File: "+self.configFile)
        self.logger.log("Language: "+ self.loc.getLoc()+"\n\n")
    def loadConfig(self):
        if os.path.exists(self.configFile) and os.path.isfile(self.configFile):
            self.logger.log(self.loc.getKey("msg_configFileLoaded"))
            with open(self.configFile, "r", encoding="utf8") as f:
                self.config = json.loads(f.read())
        else:
            self.logger.log(self.loc.getKey("msg_noConfigFile"))
            self.config["dldir"] = "./downloadedPKGs"
            self.config["verify"] = True
            self.config["checkIfAlreadyDownloaded"] = True
            self.config["storageThreshold"] = 95
            self.config["currentLoc"] = "en"
    
    def setConfig(self, config):
        self.config = config
        with open(self.configFile, "w", encoding="utf8") as f:
            f.write(json.dumps(self.config, sort_keys=True, indent=4))
        self.logger.log(self.loc.getKey("msg_configFileSaved"))
        
    def getConfig(self, key):
        if self.config[key] != None:
            return self.config[key]
    
    def loadTitleDb(self, titledb = "titledb.txt"):
        with open(titledb, "r", encoding="utf8") as f:
            data = []
            for line in f:
                item = {}
                item["id"], item["name"] = line.split("\t\t")
                if item["name"].endswith("\n"):
                    item["name"] = item["name"][:-1]
                data.append(item)
        self.titledb = data
        self.logger.log(self.loc.getKey("msg_loadedTitledb", [titledb]))
        
    def getTitleNameFromId(self, titleid=None):
        if titleid == None:
            titleid = self.titleid
        for item in self.titledb:
            if titleid == item["id"]:
                return item["name"]
    
    def getUpdates(self):
        return self.Updates[self.titleid]
    
    def checkForUpdates(self, titleid):    
        #check given id
        check = False
        titleid = titleid.upper()
        for item in self.titledb:
            if titleid == item["id"]:
                check = True
                self.titleid = titleid
                self.logger.log(self.loc.getKey("msg_titleIDIs", [item["name"], item["id"]]))
                break
        if check == False:
            self.logger.log(self.loc.getKey("msg_titleIDNotValid"), "e")
            self.titleid = ""
            return
        
        #check for updates
        updates = []
        ssl._create_default_https_context = ssl._create_unverified_context # needed for sonys self signed cert
        url = "https://a0.ww.np.dl.playstation.net/tpl/np/"+self.titleid+"/"+self.titleid+"-ver.xml"
        try:
            resp = urllib.request.urlopen(url)
        except urllib.error.HTTPError:
            self.logger.log(self.loc.getKey("msg_metaNotAvailable"), "e")
            self.titleid = ""
            return
        
        data = resp.read()
        info = data.decode('utf-8')
        #check file length for titles like BCAS20074
        if len(info) == 0:
            self.logger.log(self.loc.getKey("msg_metaFileEmpty"), "e")
            self.titleid = ""
            return
        root = ET.fromstring(info)
        if root.attrib["titleid"] == self.titleid:
            for tag in root:
                for package in tag:
                    pack = {}
                    attr = package.attrib
                    pack["version"] = attr["version"]
                    pack["size"] = attr["size"]
                    pack["sha1"] = attr["sha1sum"]
                    pack["url"] = attr["url"]
                    pack["sysver"] = attr["ps3_system_ver"]
                    updates.append(pack)
        self.Updates[titleid] = updates
    
    def downloadFiles(self):
        self.logger.log(self.loc.getKey("msg_startingDownloads"))
        i = 1
        for dl in self.DlList:
            url = dl["url"]
            sha1 = dl["sha1"]
            size = dl["size"]
            fdir = self.config["dldir"]+"/"+utils.filterIllegalCharsFilename(self.getTitleNameFromId())+"["+self.titleid+"]/"
            fname = fdir+utils.filterIllegalCharsFilename(os.path.basename(url))
            if os.path.exists(self.config["dldir"]) == False and os.path.isfile(self.config["dldir"]) == False:
                os.mkdir(self.config["dldir"])
            if os.path.exists(fdir) == False and os.path.isfile(fdir) == False:
                os.mkdir(fdir)
            skip = False
            if self.config["checkIfAlreadyDownloaded"] == True:
                #check if file already exists
                if os.path.exists(fname) and os.path.isfile(fname):
                    if int(os.path.getsize(fname)) == int(size):
                        if self.config["verify"] == False:
                            self.logger.log(self.loc.getKey("msg_alreadyDownloadedNoVerify", [os.path.basename(url)]))
                            skip = True
                        else:
                            if sha1 == self._sha1File(fname):
                                self.logger.log(self.loc.getKey("msg_alreadyDownloadedVerify", [os.path.basename(url)]))
                                skip = True
            if skip == False:
                self.logger.log(self.loc.getKey("msg_startSingleDownload", [i, len(self.DlList)]))
                self._download_file(url, fname, size)
            if self.config["verify"] == True:
                if sha1 == self._sha1File(fname):
                    self.logger.log(self.loc.getKey("msg_verifySuccess", [fname]))
                else:
                    self.logger.log(self.loc.getKey("msg_verifyFailure", [fname]))
                    os.remove(fname)
            if self.config["verify"] == False:
                self.logger.log(self.loc.getKey("msg_noVerify"))
            i += 1
            
        self.logger.log(self.loc.getKey("msg_finishedDownload", [len(self.DlList)]))
        self.DlList = []
    
    def _download_file(self, url, local_filename, size):
        total, used, free = shutil.disk_usage(os.path.dirname(local_filename))
        if used / total * 100 <= self.config["storageThreshold"]:
            if free > int(size):
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    with open(local_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192): 
                            if chunk:
                                f.write(chunk)
            else:
                self.logger.log(self.loc.getKey("msg_notEnoughDiskSpace"), "e")
        else:
            self.logger.log(self.loc.getKey("msg_spaceBelowThreshold", [100-self.storageThreshold]), "w")

    def _sha1File(self, fname):
        #copy file
        f2 = fname+"~"
        shutil.copy(fname, f2)
        with open(f2, "ab") as f:
            #remove last 32 bytes
            f.seek(-32, os.SEEK_END)
            f.truncate()
        fsha = hashlib.sha1()
        with open(f2, "rb") as f:
            for line in iter(lambda: f.read(fsha.block_size), b''):
                fsha.update(line)
        os.remove(f2)
        return fsha.hexdigest()
    
    def __del__(self):
        del self.logger

class DummyLoc():
    def getKey(self, key):
        return "ERROR \""+key+"\""