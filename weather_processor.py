##################################################################################
##
##  Weather Image Processor by Corin Buchanan-Howland
##  Description: When run, this will connect to the FTP site specified in
##      __init__ and gather any updated files from the directories specified
##      the profile file. It will process the still images into new sizes, 
##      and convert loop images to gifs and then create an animated gif from
##      them. It will then re-upload the processed files to the FTP server in
##      directories specified in the img and loop classes. 
##      Once finished, it will save copies of the still images and loop component
##      images in /stills/callLetters and /loops/callLetters respectively. Other
##      local files and remote loop files will be eliminated after use.
##      
##################################################################################
#NOTE: gd is used for nonGIF -> GIF conversion, as it is faster. ImageMagick at command line is used for animating GIFs.
#   PIL is used for other image functions -- resizing, etc. We could probably do without ImageMagick now that we have GD . . . 
#NOTE: search for EXCEPTION to find the exception for WHAS -- no max_s. I broke down and added it, since otherwise, it would look like shit. There's also an exclude list variable in the __init__ function now.
import os
from ftplib import FTP
from time import gmtime, strftime, time, mktime, strptime
from datetime import datetime
import subprocess
from shutil import move, rmtree, copy
import Image
import gd

class WeatherProcessor:
    def __init__(self):
        #vars
        self.stilltime = 0                                                 #timekeeping
        self.animtime = 0
        self.t1 = time()
        self.ftpAddy = 'origin-belo.bimedia.net'
        self.ftpLogin = 'st@belo.bimedia.net'
        self.ftpPassword = 'cruzAk5b'
        self.allowedExts = ['jpg', 'jpeg', 'gif', 'png']
        self.imageList = []
        self.excludeList = ['max_s', 'max_s.jpg', 'max_s.gif']
        
        #loop in each config array -- as profiles!
        self.path = '/var/weather/'
        self.log('Started run.')
        self.getProfiles()
        for callLetters in self.profilesDictionary:
            self.buildFolders(callLetters)
        self.getExceptionList()

#(1) First, connect to server and get files needed
        tmp = self.connectFTP()                                          
        if tmp != 0:                                                    #if ftp failed, don't try to do the rest of this.
            self.retrieveFiles()                                            
            self.closeFTP()
        self.t2 = time()                                                #timekeeper
        print 'Got files. Time elapsed: ' , self.t2 - self.t1
#(2) Process loops and stills as needed
        self.processImages() 
        self.t3 = time()                                                #timekeeper
        print 'Processed images. Time elapsed: ' , self.t3 - self.t2
#(3) Upload our changed files.
        tmp = self.connectFTP()                                            
        if tmp != 0:                                                    #if ftp failed, don't try to do the rest of this.
            self.uploadAll()                                            
            self.closeFTP()
        self.t4 = time()                                                #timekeeper
        print 'Uploaded files. Time elapsed: ' , self.t4 - self.t3
#(4) Now clean up files, clear out /new directories, etc.
        for image in self.imageList:
            image.clean()             #call each img and loop object's cleanup process.
        self.t5 = time()                                                #timekeeper
        print 'Cleanup done. Time elapsed: ' , self.t5 - self.t4
        self.t6 = time()                                                #timekeeper
        print 'All done. Time elapsed: ' , self.t6 - self.t1
        self.t7 = time()                                                #timekeeper
        print 'Time not spent in IM: ' , self.t7 - self.t1 - self.animtime - self.stilltime
        print 'Time spent in IM for stills: ' , self.stilltime
        print 'Time spent in IM for animations: ' , self.animtime
        self.log('Finished run.')
        #print 'Time spent in resize: '  ,
        #print 'Time spent in animation: ' ,
#END OF __init__. Functions and classes begin here. ###

    #######################################
    def connectFTP (self):
        self.ftp = FTP(self.ftpAddy)
        try:
            self.ftp
        except NameError:
            self.log('Connected to FTP server, but could not log in.')
            return 0
        tmp = self.ftp.login(self.ftpLogin, self.ftpPassword)
        if tmp:
            return 1
        else: 
            self.log('Could not connect to FTP server.')
            return 0

    #######################################
    def closeFTP (self):
        self.ftp.quit()

    #######################################
    def retrieveFiles (self):
        #get current time for use later
        curTime = time()
        curYear = int(datetime.now().strftime('%Y'))

        for callLetters in self.profilesDictionary:
            print 'Getting ' + callLetters
            #variables
            stillDirs = self.profilesDictionary[callLetters][0]
            stillDirArray = stillDirs.split(';')                        #unpack
            loopDirs = self.profilesDictionary[callLetters][1]
            loopDirArray = loopDirs.split(';')
            saveStills = self.profilesDictionary[callLetters][7]      #save newest image used in each loop to stills dir
            if saveStills.lower() == "true":
                saveStills = True
            localStillPath = self.path + 'stills/' + callLetters + '/'       #just for convenience
            localLoopPath = self.path + 'loops/' + callLetters + '/'
            numFrames = int(self.profilesDictionary[callLetters][3])
            
            #set up modified times dictionary
            try: 
                localStills = os.listdir(localStillPath)                    # getting list of filenames only -- no . or .. provided.
            except:
                error = 'RETRIEVE: failed to get local directory listing: ' + str(localStillPath)
                print error
                self.log(error)
                return -1
            localTimes = {}                                             #initialize
            for locStill in localStills:                                #build localTimes dictionary of current times in local directory
                localTimes[locStill] = (os.path.getmtime(localStillPath + locStill)) #gets time for local files
            
            #get stills list . . .
            #save to /stills/new/filename.ext
            for dir in stillDirArray:
                stillReturn = []                                            #we have to initialize this so that we can send a function to .dir
                dir = '/' + callLetters + dir + '/'
                try:
                    self.ftp.cwd(dir)
                except:
                    error = 'RETRIEVE: failed to change directories to ' + str(dir)
                    print error
                    self.log(error)
                    return -1
                self.ftp.dir(stillReturn.append)
                print stillReturn
                fileSizesAtStart = {}
                self.ftp.sendcmd("TYPE I")
                for still in stillReturn:                               #get file sizes here for comparison later. We need to make sure they aren't still being uploaded.
                    stillName = still[66:]
                    if stillName != '.' and stillName != '..':
                        fileSizesAtStart[stillName] = self.ftp.size(dir + stillName)
                # . . . compare w/ local list and download as needed
                for still in stillReturn:                               #now compare and download
                    stillName = still[66:]                              #grab last space-delimited chunk (i.e. name)
                    newStillName = stillName[0:-4] + stillName[-4:].lower() #lowercase extensions only.
                    stillExt = newStillName[-4:].replace('.', '')
                    if newStillName != '.' and newStillName != '..' and stillExt in self.allowedExts:
                        stillTime = still[53:65]                    #grab last 3 chunks before that (i.e. time info)
                        if stillTime.find(':') == -1:                         #if there's no colon, then this already has a year
                            tmpTime = int(mktime(strptime(stillTime, '%b %d %Y')))
                        else:
                            tmpTime = int(mktime(strptime(str(curYear) + ' '  + stillTime, '%Y %b %d %H:%M')))
                            if tmpTime > curTime:                           #if the date returned is in the future, then it's for last year. This is needed because FTP doesn't return time with file lists if time is within last year. ARGH.
                                tmpTime = int(mktime(strptime(str(curYear - 1) + ' ' + stillTime, '%Y %b %d %H:%M')))
                        self.ftp.sendcmd("TYPE I")
                        curSize = self.ftp.size(dir + stillName)
                        if curSize == fileSizesAtStart[stillName] and curSize > 0:   #Make sure the file size hasn't changed. If it did, it's still being uploaded.
                            #download the differences
                            try:
                                localTimes[newStillName]
                            except KeyError:
                                localTimes[newStillName] = 0
                            if tmpTime > localTimes[newStillName]:               #save copy of newer version locally
                                thisImagePath = localStillPath + 'new/' 
                                try: 
                                    localFile = open(thisImagePath + newStillName, 'wb')
                                except:
                                    error = 'RETRIEVE: failed to open for retrieval ' + str(thisImagePath) + str(newStillName)
                                    print error
                                    self.log(error)
                                    return -1
                                try:
                                    self.ftp.retrbinary('RETR ' + dir + stillName, localFile.write)
                                except:
                                    error = 'RETRIEVE: failed to retrieve ' + str(dir) + str(stillName) + ' or failed to write to file.'
                                    print error
                                    self.log(error)
                                    return -1
                                localFile.close()
                                x = self.img()                                  #make an image object to describe this still, and store it by call letter for easy access.
                                x.describe(callLetters, thisImagePath, newStillName, localStillPath)
                                self.imageList.append(x)
                        else:
                            self.log('file still uploading: ' + callLetters + '|' + stillName)
            
            #Loops are simpler. We'll just get every new file and then delete it.
            #We'll save files to /loops/new/loopname/int(currentepoch)filename.ext
            for dir in loopDirArray:                                    #loop on dirs in config
                dir = '/' + callLetters + dir + '/'
                loopDirReturn = []
                self.ftp.cwd(dir)
                self.ftp.dir(loopDirReturn.append)
                for loopDir in loopDirReturn:                           #loop on directories in above
                    loopDir = loopDir[66:]
                    if loopDir != '.' and loopDir != '..':
                        thisDir = []
                        self.ftp.cwd(dir + loopDir)
                        self.ftp.dir(thisDir.append)
                        fileSizesAtStart = {}
                        self.ftp.sendcmd("TYPE I")
                        for image in thisDir:                               #get file sizes here for comparison later. We need to make sure they aren't still being uploaded.
                            imageName = image[66:]
                            if imageName != '.' and imageName != '..':
                                fileSizesAtStart[imageName] = self.ftp.size(dir + loopDir + '/' + imageName)
                        x = self.loop()
                        filesExist = 0                                  #we'll use this to determine if any real files were in this dir
                        for file in thisDir:                                #loop on files in those directories
                            fileName = file[66:]
                            newFileName = fileName[0:-4] + fileName[-4:].lower() #lowercase extensions only.
                            if fileName not in self.excludeList: #EXCEPTION! UGH!
                                fileExt = newFileName.split('.')[-1]
                                if fileExt in self.allowedExts:
                                    self.ftp.sendcmd("TYPE I")
                                    curSize = self.ftp.size(dir + loopDir + '/' + fileName)
                                    if  curSize == fileSizesAtStart[fileName] and curSize > 0:
                                        filesExist = 1
                                        thisImageFolder = localLoopPath + 'new/' + loopDir + '/'
                                        thisImageName = str(int(time())) + newFileName[0:-4] + '.' + fileExt
                                        thisImageDestination = localLoopPath
                                        if os.path.exists(thisImageFolder) == False:        #make this folder if it doesn't already exist.
                                            os.mkdir(thisImageFolder)
                                        #print 'DEBUG: saving to ' + thisImageFolder + thisImageName
                                        try:
                                            localFile = open(thisImageFolder + thisImageName, 'wb')
                                        except:
                                                error = 'RETRIEVE: failed to open for retrieval ' + str(thisImageFolder) + str(thisImageName)
                                                print error
                                                self.log(error)
                                                return -1
                                        serverFilePath = dir + loopDir + '/' + fileName
                                        self.ftp.retrbinary('RETR ' + serverFilePath, localFile.write)
                                        localFile.close()
                                        if os.path.exists(thisImageFolder + thisImageName):     #let's make sure we actually got the file before going further
                                            self.ftp.delete(serverFilePath)
                                            if saveStills is True:
                                                copyPath = localStillPath + 'new/'
                                                copyName = loopDir + '.' + fileExt
                                                copy(thisImageFolder + thisImageName, copyPath + copyName)
                                                y = self.img()
                                                y.describe(callLetters, copyPath, copyName, localStillPath)
                                                self.imageList.append(y)
                                            #for non-gifs, convert them now to save time later.
                                            if thisImageName[-4:] != '.gif':                     #don't switch to gif if it already is a gif. Duh.
                                                newName = thisImageName[0:-4] + '.gif'
                                                #print'DEBUG: Still = ' + still
                                                try: 
                                                    f = open(thisImageFolder + newName, 'w')
                                                except:
                                                    error = 'RETRIEVE: failed to open for GIF conversion ' + str(thisImageFolder) + str(newName)
                                                    print error
                                                    self.log(error)
                                                    return -1
                                                t = time()                              #timekeeping
                                                image = gd.image(thisImageFolder + thisImageName)
                                                image.writeGif(f)
                                                self.stilltime += time() - t            #timekeeping
                                                f.close()
                                                os.remove(thisImageFolder + thisImageName)
                                                thisImageName = newName
                                            #aaaand add it to the gif roster
                                            if x.numImg() < numFrames:
                                                #print 'DEBUG: added this image'
                                                x.addImg(thisImageName)
                                        else:
                                            print 'File did not successfully download. ' + fileName
                                            self.log('File did not successfully download. ' + fileName)
                                    else:
                                        self.log('File currently still uploading: ' + fileName)
                                        
                        if filesExist == 1:
                            #make a loop object to describe this loop, and store it by call letter for easy access.
                            x.describe(callLetters, thisImageFolder, loopDir, loopDir + '.gif', thisImageDestination)
                            #now we need to make sure this loop has enough images . . .
                            #set up modified times dictionary
                            savedImgs = os.listdir(x.extraDest)          # getting list of filenames only -- no . or .. provided.
                            if savedImgs != [] and x.numImg() < numFrames:
                                savedImageTime = []                                   #initialize
                                for img in savedImgs:                            #build localTimes dictionary of current times in local directory
                                    savedImageTime.append({os.path.getmtime(x.extraDest + img):img}) #gets time for local files
                                    savedImageTime.sort()
                                    savedImageTime.reverse()                          #newest first
                                #take sorted list, and if we need another image, peel off the first time:image pair and return the image, then add it to loop obj.
                                for imgTimeDict in savedImageTime:
                                    for key in imgTimeDict:
                                        appendImg = imgTimeDict[key]
                                        #'DEBUG: added image from archive: ' + x.extraDest + appendImg
                                        if x.numImg() < numFrames:
                                            try:                                            
                                                copy(x.extraDest + appendImg, x.path + appendImg) 
                                            except:
                                                error = 'RETRIEVE: failed to copy ' + str(x.extraDest) + str(appendImg) + ' to ' + str(x.path) + str(appendImg)
                                                print error
                                                self.log(error)
                                                return -1
                                            x.addImg(appendImg)
                                        else:
                                            os.remove(x.extraDest + appendImg)     #get rid of any extra frames.
                            self.imageList.append(x)


    #######################################
    def processImages(self):
        for callLetters in self.profilesDictionary:
            #variables
            sizes = self.profilesDictionary[callLetters][2]
            sizesArray = sizes.split(';')
            numFrames = self.profilesDictionary[callLetters][3]         #this goes somewhere else
            duration = self.profilesDictionary[callLetters][4]
            endDelay = self.profilesDictionary[callLetters][5]          #this variable sets the delay on the last image. Default is null, for 'don't use this setting'.
            topRadar = self.profilesDictionary[callLetters][6]          #radar for right column - make a 300x225 version
            tmpImageList = []                                           #duplicating because we're going to add things to it in the middle of a for in loop on it
            tmpImageList.extend(self.imageList)                         #doin' like this because we don't want to pass by reference.

            for imageData in tmpImageList:
                if imageData.callLetters == callLetters:                    #this is a bit of a hack . . . might be able to make this more efficient.
                    #extract variables -- just cleaner this way
                    path = imageData.path
                    name = imageData.name
                    destination = imageData.destination

                    #STILLS
                    if imageData.isLoop == False:
                        print 'Processing still ' , path + name
                        i = 1
                        if name in self.exceptionList:
                            thisSizesArray = self.exceptionList[name][0].split(';')
                        else:
                            thisSizesArray = sizesArray
                        for newSize in thisSizesArray:
                            self.stillResize(i, newSize, path, name, callLetters, destination)
                            i += 1
                    #LOOPS
                    elif imageData.isLoop == True:
                        includeImages = []
                        #assemble list of images, making sure to honor correct delays
                        if endDelay != '0':     #honor endDelay if it exists                          
                            for image in imageData.images:
                                if image == imageData.images[-1]:
                                    lastImage = image               #lastImage is the one to add delay on
                                else:
                                    includeImages.append(image)
                        else:                                       #otherwise, uniform delay
                            for image in imageData.images:
                                includeImages.append(image)
                        #resample each image, and save to special folder
                        newDir = path + 'tmp/'
                        if os.path.exists(newDir) == False:
                            os.mkdir(newDir)
                        self.tmpData = {}
                        for still in includeImages:
                            if name in self.exceptionList:
                                thisSizesArray = self.exceptionList[name][0].split(';')
                            else:
                                thisSizesArray = sizesArray
                            for newSize in thisSizesArray:
                                self.loopResize(newSize, newDir, path, still)
                            if imageData.name[0:-4] == topRadar:
                                self.loopResize('300x225', newDir, path, still)
                        #now we've got a directory of callLetters/loop/tmp/ filled with subdirs named after sizes, filled with versions of this img in the MIFF format.
                        for dir in self.tmpData:
                            size = dir.split('/')[-2]
                            if size == sizesArray[0]:                    #I sure wish we didn't have this stupid naming structure.
                                ext = '.gif'
                            elif size == sizesArray[1]:
                                ext = '_thumb.gif'    
                            else: 
                                ext = '_' + size + '.gif'
                            finalImgName = self.path + 'loops/' + callLetters + '/' + imageData.loop + ext
                            self.tmpData[dir].reverse()
                            tmp = self.animate(finalImgName, self.tmpData[dir], size, duration, endDelay)
                            if tmp != False and ext != '.gif':
                                imageData.addSize(finalImgName)
                        #clean up our mess
                        for dir in self.tmpData:
                            for still in os.listdir(dir):
                                os.remove(dir + still)
                            os.rmdir(dir)
                        try:
                            os.rmdir(newDir)
                        except:
                            error = 'process: failed to remove dir ' + str(newDir)
                            print error
                            self.log(error)

    #######################################
    def stillResize(self, i, newSize, path, name, callLetters, destination):
        tmp = newSize.split('x')
        tSize = (int(tmp[0]), int(tmp[1]))          #tSize is newSize as a tuple of ints for comparison purposes.
        t = time()                                  #timekeeping
        #open the image
        try:
            image = Image.open(path + name)
        except:
            error = 'PROCESS: failed to open image file ' + str(path) + str(name)
            print error
            self.log(error)
            return -1
        if i == 1 and image.size != tSize:          #don't resize if it's already the right size.
            newName = name
            try:
                image = image.resize(tSize)
            except:
                error = 'PROCESS: failed to resize ' + str(path) + str(name)
                print error
                self.log(error)
                return -1
            image.save(path + newName)
        elif i == 2:
            newName = name[0:-4] + '_thumb' + name[-4:]
            try:
                image = image.resize(tSize)
            except:
                error = 'PROCESS: failed to resize ' + str(path) + str(name)
                print error
                self.log(error)
                return -1
            image.save(path + newName)
        elif i > 2:
            newName = name[0:-4] + '_' + newSize + name[-4:]
            try:
                image = image.resize(tSize)
            except:
                error = 'PROCESS: failed to resize ' + str(path) + str(name)
                print error
                self.log(error)
                return -1
            image.save(path + newName)
        self.stilltime += time() - t                #timekeeping
        #add it to the roster.
        if i > 1:
            x = self.img()
            x.describe(callLetters, path, newName, destination) #for each copy image, we use mostly source settings, and only update the name)
            self.imageList.append(x)

    #######################################
    def loopResize(self, newSize, newDir, path, still):
        tmp = newSize.split('x')
        tSize = (int(tmp[0]), int(tmp[1]))      #tSize is newSize as a tuple of ints for comparison purposes.
        thisNewDir = newDir + newSize + '/'
        if os.path.exists(thisNewDir) == False:
            os.mkdir(thisNewDir)
        try:
            self.tmpData[thisNewDir]
        except KeyError:
            self.tmpData[thisNewDir] = []
        t = time()                              #timekeeping
        try:
            image = Image.open(path + still)
        except:
            print 'failed to resize. Does' , path + still , ' exist? ' , os.path.exists(path + still)
            error = 'PROCESS: could not resize ' + str(path) + str(still)
            print error
            self.log(error)
            return -1
        image = image.resize(tSize)
        image.save(thisNewDir + still)
        self.stilltime += time() - t            #timekeeping
        self.tmpData[thisNewDir].append(thisNewDir + still)
    #######################################
    def animate(self, name, images, size, delay = '100', endDelay = '0'):
        print 'Animating ' + name
        callString = 'convert -loop 0 -delay ' + delay + ' -size ' + size + ' ' 
        if endDelay != '0':
            for image in images[0:-1]:
                callString += image + ' '
            callString += '-delay ' + endDelay + ' ' + images[-1] + ' '
        else:
            for image in images:
                callString += image + ' '
        callString += name
        t = time()                                                      #timekeeping: log IM time
        tmp = subprocess.call(callString.split())
        self.animtime += time() - t                                     #timekeeping: log IM time
        if tmp != 0:
            self.log(name + ' failed to animate.')
            return False
        else:
            return True

    #######################################
    def uploadAll (self):
        for image in self.imageList:
            if image.isLoop == False:
                try: 
                    file = open(image.path + image.name, 'rb')
                except:
                    error = 'failed to open for upload ' + str(image.path) + str(image.name)
                    print error
                    self.log(error)
                    return -1
                self.ftp.storbinary('STOR ' + image.ftpPath + image.name, file)
                file.close()
            else:
                try:
                    file = open(image.destination + image.name, 'rb')
                except:
                    error = 'failed to open for upload ' + str(image.destination) + str(image.name)
                    print error
                    self.log(error)
                    return -1
                self.ftp.storbinary('STOR ' + image.ftpPath + image.name, file) #loops have already moved to destination by now . . .
                file.close()
                for sizeName in image.otherSizes:
                    name = sizeName.split('/')[-1]
                    try:
                        file = open(sizeName, 'rb')
                    except:
                        error = 'failed to open for upload ' + str(sizeName)
                        print error
                        self.log(error)
                        return -1
                    self.ftp.storbinary('STOR ' + image.ftpPath + name, file)
                    file.close()

    #######################################
    def log (self, error):
        logPath = self.path + 'log/error.log'
        logFile = open(logPath, 'a')
        logFile.write(strftime('%Y-%m-%d %H:%M:%S ', gmtime()) + error + '\n')
        logFile.close()
    
    #######################################
    def getProfiles (self):
        profilesPath = self.path + 'profiles/'                          
        self.profilesDictionary = {}
        try:
            profiles = open(profilesPath + 'profiles.txt', 'r')
        except: 
            self.log('NO PROFILES FOUND. PLEASE BUILD profiles.txt in ' + profilesPath + '.')
            return -1
        for p in profiles:
            if p[0] != '#':                                             #filter out lines starting w/ pound symbol
                temp = p.split('|')
                self.profilesDictionary[temp[0]] = temp[1:]
        profiles.close()
        
    #######################################
    def getExceptionList (self):
        exceptionsPath = self.path + 'profiles/'                          
        self.exceptionList = {}
        try:
            exceptions = open(exceptionsPath + 'exceptions.txt', 'r')
        except: 
            self.log('NO EXCEPTIONS FOUND. PLEASE BUILD exceptions.txt in ' + exceptionsPath + '.')
            return -1
        for e in exceptions:
            if e[0] != '#':                                             #filter out lines starting w/ pound symbol
                temp = e.split('|')
                self.exceptionList[temp[0]] = temp[1:]
        exceptions.close()
    
    #######################################
    #this function just builds out the necessary folders, in case they don't exist.
    def buildFolders(self, callLetters):
        folders = [self.path + 'stills/']
        folders.append(self.path + 'stills/' + callLetters + '/')
        folders.append(self.path + 'stills/' + callLetters + '/' + 'new/')
        folders.append(self.path + 'loops/')
        folders.append(self.path + 'loops/' + callLetters + '/')
        folders.append(self.path + 'loops/' + callLetters + '/' + 'new/')
        for folder in folders:
            if os.path.exists(folder) != True:
                os.mkdir(folder)

    #######################################
    class img:
        def __init__(self):
            self.isLoop = False
        def clean(self):
            try:
                move(self.path + self.name, self.destination + self.name)
            except:
                error = 'IMG: failed to move ' + str(self.path) + str(self.name) + ' to ' + str(self.destination) + str(self.name)
                print error
                self.log(error)
        def describe(self, callLetters, path, name, destination):
            self.callLetters = callLetters
            self.path = path
            self.name = name
            self.destination = destination
            self.ftpPath = '/' + self.callLetters + '/weather/stills/'
        def log (self, error):
            logPath = '/var/weather/log/error.log'
            logFile = open(logPath, 'a')
            logFile.write(strftime('%Y-%m-%d %H:%M:%S ', gmtime()) + error + '\n')
            logFile.close()
    
    #######################################
    class loop:
        def __init__(self):
            self.images = []
            self.otherSizes = []
            self.isLoop = True
        def clean(self):
            #delete any stored images we didn't use, delete the animated images we made, remove the folder in /new.
            oldAnims = os.listdir(self.destination)
            for deleteMe in oldAnims:
                if deleteMe.find('gif') != -1: 
                    os.remove(self.destination + deleteMe)
            for image in self.images:
                if os.path.exists(self.extraDest + image) is False:     #only move back images that aren't already there
                    try:
                        move(self.path + image, self.extraDest + image)
                    except:
                        error = 'LOOP/clean: failed to move ' + str(self.path) + str(image) + ' to ' + str(self.extraDest) + str(image)
                        print error
                        self.log(error)
                else:
                    os.remove(self.path + image)
            try:
                rmtree(self.path)
            except:
                error = 'LOOP/clean: could not remove directory ' + str(self.path)
                print error
                self.log(error)
        def describe(self, callLetters, path, loop, name, destination):
            self.callLetters = callLetters
            self.path = path
            self.loop = loop
            self.name = name
            self.destination = destination
            self.ftpPath = '/' + self.callLetters + '/weather/animated-loops/'
            self.extraDest = self.destination + self.loop + '/'
            if os.path.exists(self.extraDest) != True:
                os.mkdir(self.extraDest)
        def addSize(self, image):
            self.otherSizes.append(image)
        def addImg(self, image):
            self.images.append(image)
        def numImg(self):
            return len(self.images)
        def log (self, error):
            logPath = '/var/weather/log/error.log'
            logFile = open(logPath, 'a')
            logFile.write(strftime('%Y-%m-%d %H:%M:%S ', gmtime()) + error + '\n')
            logFile.close()
        def getImgs(self):
            for image in self.images:
                try:
                    move(self.extraDest + image, self.path + image)
                except:
                    error = 'LOOP/getImgs: failed to move ' + str(self.extraDest) + str(image) + ' to ' + str(self.path) + str(image)
                    print error
                    self.log(error)

#######################################
def main():
    wp = WeatherProcessor()

if __name__ == '__main__':
    main()
