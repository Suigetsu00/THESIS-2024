import os
import cv2
import sys
import serial
import shutil
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QPushButton, QLineEdit, QPlainTextEdit
from PyQt5.QtCore import QTimer
from PyQt5 import uic
from PyQt5.QtGui import QImage, QPixmap
from functools import partial
from pydub import AudioSegment, playback

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import resources

OS_LINUX = 'linux'
OS_WINDOWS = 'windows'
OS_MACOS = 'macos'

if sys.platform == 'linux':
    OS = OS_LINUX
elif sys.platform == 'win32':
    OS = OS_WINDOWS
elif sys.platform == 'darwin':
    OS = OS_MACOS


# Instantiate main pyqt5 window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Parameters
        self.databasePath = "../../database"
        self.usersPath = "../../users"
        os.makedirs(self.databasePath, exist_ok=True)
        os.makedirs(self.usersPath, exist_ok=True)
        if not os.path.exists('scorethresh.txt'):
            with open('scorethresh.txt', 'w') as f:
                f.write('30')

        # Serial object
        if OS == OS_LINUX:
            self.serial = serial.Serial('/dev/ttyACM0', 9600)

        # The current drawing that needs to be traced
        self.currentDrawing = None
        
        # The current sketch of the child
        self.childSketch = None

        # The combined image of the currentDrawing and the image
        self.combinedImage = None

        # Drawing State
        self.isDrawing = False

        # Pencil or Erase
        self.tool = 'pencil' # 'pencil' or 'eraser'

        # Gray value for the combined image
        self.grayValue = 0

        # For this window, load the UI from gui.ui file
        uic.loadUi('thesisUi.ui', self)

        # Reset the drawing area
        self.resetDrawingArea()

        # Show blank image on the drawing preview
        self.showWhiteImageOnDrawingPreview()

        # Load score thresh
        with open('scorethresh.txt', 'r') as f:
            self.scoreThresh = int(f.read())
        self.editScoreThresh.setText(str(self.scoreThresh))

        # Create a function for the drawingArea to handle click and drag events
        # Draw the path taken by the mouse while dragging
        self.drawingArea.mouseMoveEvent = self.mouseMoveEvent
        self.drawingArea.mousePressEvent = self.mousePressEvent
        self.drawingArea.mouseReleaseEvent = self.mouseReleaseEvent

        # ============== Home Page ==============
        self.btnStart.clicked.connect(lambda: self.stackedWidget.setCurrentWidget(self.pgEnterName))
        self.btnManage.clicked.connect(self.loginAsAdmin)
        self.btnShutDown.clicked.connect(self.shutDown)
        # =======================================

        # ============== Password Page ==============
        self.btnLoginAsAdmin.clicked.connect(self.goToManage)
        self.btnCancelAdminLogin.clicked.connect(lambda: self.stackedWidget.setCurrentWidget(self.pgHome))

        # ============== Enter Name Page ==============
        self.btnEnterName.clicked.connect(self.validateName)
        self.btnNameCancel.clicked.connect(lambda: self.stackedWidget.setCurrentWidget(self.pgHome))
        # =======================================

        # ============= Level Selection Page ==============
        self.btnSelectCancel.clicked.connect(lambda: self.stackedWidget.setCurrentWidget(self.pgEnterName))
        self.btnSelectProceed.clicked.connect(self.selectProceed)
        # - select event on listSelectCategory
        self.listSelectCategory.itemSelectionChanged.connect(self.refreshSelectLevels)
        # - select event on listSelectLevel
        self.listSelectLevel.itemSelectionChanged.connect(self.refreshSelectImages)

        # =======================================


        # ============= Instructions Page ==============
        self.btnStartDrawing.clicked.connect(self.startDrawing)

        # =======================================


        # ============== Manage Page ==============
        self.btnExitManage.clicked.connect(lambda: self.stackedWidget.setCurrentWidget(self.pgHome))
        
        self.btnAddCategory.clicked.connect(self.addCategory)
        self.btnDeleteCategory.clicked.connect(self.deleteCategory)

        self.btnAddLevel.clicked.connect(self.addLevel)
        self.btnDeleteLevel.clicked.connect(self.deleteLevel)
        self.btnSaveInstructions.clicked.connect(self.saveInstructions)

        self.btnAddDrawing.clicked.connect(self.addDrawing)
        self.btnDeleteDrawing.clicked.connect(self.deleteDrawing)

        # - select event on listCategories
        self.listCategories.itemSelectionChanged.connect(self.refreshManageLevels)
        # - select event on listLevels
        self.listLevels.itemSelectionChanged.connect(self.refreshManageImages)
        # - select event on listImages
        self.listImages.itemSelectionChanged.connect(self.manageShowImage)

        self.btnManageScoreThresh.clicked.connect(self.updateScoreThresh)

        # =======================================

        # ============== Drawing Page ==============
        self.btnCalculateScore.clicked.connect(self.calculateScore)
        self.btnChooseDraw.clicked.connect(self.setToolToPencil)
        self.btnChooseErase.clicked.connect(self.setToolToEraser)
        self.btnBackFromDrawing.clicked.connect(self.backFromDrawing)
        # =======================================
        
        # ============== Job Well Done Page ==============
        self.btnContinueSuccess.clicked.connect(self.continueAfterSuccess)
        self.btnPlayResult.clicked.connect(lambda: playback.play(self.currentAudio))
        # =======================================


        # ============== Show Keyboard Event ==============
        self.editEnterName.mousePressEvent = lambda event: self.showKeyboard(self.editEnterName)
        self.editNewCategory.mousePressEvent = lambda event: self.showKeyboard(self.editNewCategory)
        self.editNewLevel.mousePressEvent = lambda event: self.showKeyboard(self.editNewLevel)
        self.editNewDrawing.mousePressEvent = lambda event: self.showKeyboard(self.editNewDrawing)
        self.editScoreThresh.mousePressEvent = lambda event: self.showKeyboard(self.editScoreThresh)
        self.editInstructions.mousePressEvent = lambda event: self.showKeyboard(self.editInstructions)
        self.editPassword.mousePressEvent = lambda event: self.showKeyboard(self.editPassword, password=True)
        # =======================================

        # Keyboard Shortcuts
        # listObjs = dir(self)
        # for obj in listObjs:
        #     if obj.startswith('kb_'):
        #         btn = getattr(self, obj)
        #         target = getattr(self, obj.replace('kb_', ''))
        #         btn.clicked.connect(partial(self.fcnKeyboard, target))

    
         # ============== Keyboard Page ==============
        # Keyboard Keys
        kbKeys = self.pgKeyboard.children()
        kbChars = [kbKey for kbKey in kbKeys if
            type(kbKey) == QPushButton and
            kbKey.text() != 'SHIFT' and
            kbKey.text() != 'DONE' and
            kbKey.text() != 'ERASE' and
            kbKey.text() != '-' and
             kbKey.text() != '!' and
            kbKey.text() != 'SPACE']

        kbShift = [kbKey for kbKey in kbKeys if
            type(kbKey) == QPushButton and
            kbKey.text() == 'SHIFT'][0]
        
        kbDone = [kbKey for kbKey in kbKeys if
            type(kbKey) == QPushButton and
            kbKey.text() == 'DONE'][0]
        
        kbErase = [kbKey for kbKey in kbKeys if
            type(kbKey) == QPushButton and
            kbKey.text() == 'ERASE'][0]
        
        kbSpace = [kbKey for kbKey in kbKeys if
            type(kbKey) == QPushButton and
            kbKey.text() == 'SPACE'][0]

        kbDash = [kbKey for kbKey in kbKeys if
            type(kbKey) == QPushButton and
            kbKey.text() == '-'][0]
        kbMark = [kbKey for kbKey in kbKeys if
            type(kbKey) == QPushButton and
            kbKey.text() == '!'][0]
        
        kbShift.clicked.connect(lambda: self.fcnKbShift(kbChars))
        
        for kbChar in kbChars:
            kbChar.clicked.connect(partial(self.fcnKbChar, kbChar))

        kbErase.clicked.connect(self.fcnKbErase)

        kbDone.clicked.connect(self.fcnKbDone)

        kbSpace.clicked.connect(self.fcnKbSpace)

        kbDash.clicked.connect(self.fcnKbDash)

        kbMark.clicked.connect(self.fcnKbMark)


    def keyboardPress(self, text):
        currentText = self.target.text()
        self.target.setText(currentText + text)


    def showKeyboard(self, target, password=False):
        if password:
            self.kbEditPrompt.setEchoMode(QLineEdit.Password)
        else:
            self.kbEditPrompt.setEchoMode(QLineEdit.Normal)

        # Get the current text on the target
        # If target is of type QLineEdit
        if type(target) == QLineEdit:
            self.kbEditPrompt.setText(target.text())
        elif type(target) == QPlainTextEdit:
            self.kbEditPrompt.setText(target.toPlainText())
        else:
            return
        
        self.kbLastPage = self.stackedWidget.currentWidget()
        self.kbTarget = target
        self.stackedWidget.setCurrentWidget(self.pgKeyboard)


    def setToolToPencil(self):
        self.tool = 'pencil'
        # Set self.lblDrawEraseIndicator y position to 200 
        self.lblDrawEraseIndicator.move(self.lblDrawEraseIndicator.x(), 200)
    
    def setToolToEraser(self):
        # Set self.lblDrawEraseIndicator y position to 310
        self.tool = 'eraser'
        self.lblDrawEraseIndicator.move(self.lblDrawEraseIndicator.x(), 310)


    def updateScoreThresh(self):
        # Validate
        if len(self.editScoreThresh.text()) == 0:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please enter a number.")
            msg.exec_()
            return

        try:
            scoreThresh = int(self.editScoreThresh.text())
        except:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please enter a valid number.")
            msg.exec_()
            return
        
        if scoreThresh < 0 or scoreThresh > 100:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please enter a number between 0 and 100.")
            msg.exec_()
            return
        
        with open('scorethresh.txt', 'w') as f:
            f.write(str(scoreThresh))
        
        self.scoreThresh = scoreThresh

        msg = QMessageBox()
        msg.setWindowTitle("Success")
        msg.setText("Score threshold updated successfully.")

        msg.exec_()





    def loginAsAdmin(self):
        self.stackedWidget.setCurrentWidget(self.pgPassword)


    def goToManage(self):
        # Get the password from editPassword
        password = self.editPassword.text()

        if password != "visual24680":
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Incorrect password.")
            msg.exec_()
            return


        # Update scorethresh
        with open('scorethresh.txt', 'r') as f:
            self.scoreThresh = int(f.read())
        self.editScoreThresh.setText(str(self.scoreThresh))

        self.refreshManageCategories()
        self.stackedWidget.setCurrentWidget(self.pgManage)
    


    def validateName(self):

        # Get the name from the input field
        name = self.editEnterName.text().strip().upper()

        # Validate
        # - Check if the name is empty
        if len(name) == 0:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please enter a name.")
            msg.exec_()
            return

        # Create directory if it does not exist
        os.makedirs(os.path.join(self.usersPath, name), exist_ok=True)
        
        #TODO: user progress data
        self.currentUser = name

        # Show the level selection page
        self.showLevelSelectionPage()
    

    def showLevelSelectionPage(self):
        self.refreshSelectCategories()
        
        self.stackedWidget.setCurrentWidget(self.pgSelection)




    def calculateScore(self):
        # Convert the image to pure black and white
        self.currentDrawing[self.currentDrawing < 128] = 0
        self.currentDrawing[self.currentDrawing >= 128] = 255

        self.childSketch[self.childSketch < 128] = 0
        self.childSketch[self.childSketch >= 128] = 255

        # Perform AND(NOT, NOT) operation
        matches = cv2.bitwise_and(cv2.bitwise_not(self.currentDrawing), cv2.bitwise_not(self.childSketch))

        # Perform AND( , NOT) operation
        nonMatches = cv2.bitwise_and(self.currentDrawing, cv2.bitwise_not(self.childSketch))

        # Get the number of matched pixels in the result
        matchPixels = np.sum(matches[:,:,0] == 255)

        # Get the number of non-matched pixels in the result
        nonMatchPixels = np.sum(nonMatches[:,:,0] == 255)

        # Get the number of total pixels in the currentDrawing
        totalPixels = np.sum(self.currentDrawing[:,:,0] == 0)

        # Calculate the score
        score = ((matchPixels - nonMatchPixels) / totalPixels) * 100

        if score < 0:
            score = 0
        
        if score < self.scoreThresh:
            # Display try again
            msg = QMessageBox()
            msg.setWindowTitle("Try Again")
            msg.setText("<p><span style='font-size: 18px; font-weight: bold;'>Please try again.</span></p>")
            msg.setIcon(QMessageBox.Warning)
            msg.setStyleSheet("""
                QMessageBox {
                background-color: #f2f2f2;
                color: #333;
                font-family: Arial, sans-serif;
                font-size: 18px;
                padding: 20px;
                border: 1px solid #ccc;
                border-radius: 10px;
                width: 2000;
                height: 1500;
                }
    
                QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
                }       
    
                QPushButton:hover {
                background-color: #45a049;
                }
                """)
            msg.exec_()

            self.resetDrawingArea()
            self.startDrawing()

            return  

        self.score = score

        # Show the combined image to lblImgResults
        self.showCVImage(self.combinedImage, self.lblImgResults)
        
        # Audio segment file
        self.currentAudio = AudioSegment.from_file(os.path.join(self.databasePath, self.currentCategory, self.currentLevel, self.currentImage + '.mp3'))

        print("Calculating:", self.currentImage)

        # Save the score
        userDirectory = os.path.join(self.usersPath, self.currentUser, self.currentCategory, self.currentLevel)
        os.makedirs(userDirectory, exist_ok=True)

        with open(os.path.join(userDirectory, self.currentImage + '.txt'), 'w') as f:
            f.write(str(score))

        # Check if all selectListDrawing items have been completed, except for the current one
        allCompleted = True
        for i in range(self.listSelectDrawing.count()):
            item = self.listSelectDrawing.item(i)
            currentText = item.text() if not item.text().startswith('✓') else item.text()[2:]
            # Skip the current item
            if currentText == self.currentImage:
                if item.text().startswith('✓'):
                    allCompleted = False
                    break
                continue

            if not item.text().startswith('✓'):
                allCompleted = False
                break
        
        if allCompleted:
            # Show blocking dialog message
            # Must be modal
            msg = QMessageBox()
            msg.setWindowTitle("Prize")
            msg.setText("<p><span style='font-size: 24px; font-weight: bold;'>You won a prize!</span></p>")
            msg.setStyleSheet("""
                QMessageBox {
                background-color: #f2f2f2;
                color: #333;
                font-family: Arial, sans-serif;
                font-size: 18px;
                padding: 20px;
                border: 1px solid #ccc;
                border-radius: 10px;
                }
                QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
                }
                QPushButton:hover {
                background-color: #45a049;
                }
                """)
            msg.exec_()

            # Dispense
            if OS == OS_LINUX:
                self.serial.write(b'dispense\n')
            else:
                print("Dispensing...")
        
        # If the current item in the listSelectDrawing does not have a check mark, add a check mark
        currentItem = self.listSelectDrawing.currentItem()
        if not currentItem.text().startswith('✓'):
            currentItem.setText('✓ ' + currentItem.text())

        self.stackedWidget.setCurrentWidget(self.pgSuccess)

        def fcnPlayAudio():
            playback.play(self.currentAudio)
        
        QTimer.singleShot(10, fcnPlayAudio)






    def resetDrawingArea(self):
        # Reset the image
        drawingAreaSize = self.drawingArea.size()
        blankImage = np.ones((drawingAreaSize.height(), drawingAreaSize.width(), 3), np.uint8) * 255
        self.childSketch = blankImage.copy()
        self.currentDrawing = blankImage.copy()
        self.combinedImage = blankImage.copy()

        # Display the image on the label
        self.displayImage()

    def start(self):
        
        # Reset the image
        self.resetDrawingArea()

        # Load the image from the dataset
        img = cv2.imread('../../images/test/test.jpg')

        # Convert the image to pure black and white
        img[img < 128] = 0
        img[img >= 128] = 255

        # Set the current drawing
        self.currentDrawing = img.copy()

        # Make a copy of the current drawing
        self.combinedImage = self.currentDrawing.copy()

        # Lighten the black pixels to light gray
        self.combinedImage[self.combinedImage == 0] = 240

        # Display the image on the label
        self.displayImage()

        self.stackedWidget.setCurrentWidget(self.pgDraw)
    
    # Function to display the image on the label
    def displayImage(self):
        # Resize the image to the size of the label
        self.combinedImage = cv2.resize(self.combinedImage, (self.drawingArea.width(), self.drawingArea.height()))
        # Convert the image to RGB format
        qImg = cv2.cvtColor(self.combinedImage, cv2.COLOR_BGR2RGB)
        # Convert the image to QImage format
        qImg = QImage(qImg.data, qImg.shape[1], qImg.shape[0], QImage.Format_RGB888)
        # Set the image to the label
        self.drawingArea.setPixmap(QPixmap.fromImage(qImg))
    

    def showCVImage(self, imgCV, widget):
        # Create copy
        img = imgCV.copy()
        # Resize the image to the size of the label
        img = cv2.resize(img, (widget.width(), widget.height()))
        # Convert the image to RGB format
        qImg = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # Convert the image to QImage format
        qImg = QImage(qImg.data, qImg.shape[1], qImg.shape[0], QImage.Format_RGB888)
        # Set the image to the label
        widget.setPixmap(QPixmap.fromImage(qImg))


    # Function to handle mouse press event
    def mousePressEvent(self, event):
        self.prevPos = event.pos()
        self.isDrawing = True

    # Function to handle mouse release event
    def mouseReleaseEvent(self, event):
        self.isDrawing = False

    # Function to handle mouse move event
    def mouseMoveEvent(self, event):
        if self.isDrawing:
            # Get the current position of the mouse
            currentPos = event.pos()
            # print(self.prevPos.x(), self.prevPos.y(), currentPos.x(), currentPos.y())
            # Draw a line from the previous position to the current position
            if self.tool == 'pencil':
                cv2.line(self.childSketch, (self.prevPos.x(), self.prevPos.y()), (currentPos.x(), currentPos.y()), (0, 0, 0), 8)
            elif self.tool == 'eraser':
                cv2.line(self.childSketch, (self.prevPos.x(), self.prevPos.y()), (currentPos.x(), currentPos.y()), (255, 255, 255), 8)
            # Update the previous position
            self.prevPos = currentPos

            # Combine the current drawing and the child sketch
            self.combinedImage = self.currentDrawing.copy()
            # Lighten the black pixels to light gray
            self.combinedImage[self.combinedImage == 0] = self.grayValue

            self.combinedImage[:,:,0][self.childSketch[:,:,0] == 0] = 255
            self.combinedImage[:,:,1][self.childSketch[:,:,0] == 0] = 0
            self.combinedImage[:,:,2][self.childSketch[:,:,0] == 0] = 0
            

            # Display the image on the label
            self.displayImage()
    


    # ============ pgKeyboard ============
    def fcnKeyboard(self, target):
        self.kbTarget = target
        self.kbLastPage = self.stackedWidget.currentWidget()
        self.kbEditPrompt.setText(target.text())
        self.stackedWidget.setCurrentWidget(self.pgKeyboard)
        
    def fcnKbShift(self, kbChars):
        letterAKey = [kbChar for kbChar in kbChars if kbChar.text() in ['a', 'A']][0]
        isUpper = letterAKey.text().isupper()
        
        for kbChar in kbChars:
            kbChar.setText(kbChar.text().lower() if isUpper else kbChar.text().upper())
            kbChar.repaint()

    def fcnKbChar(self, kbChar):

        self.kbEditPrompt.setText(self.kbEditPrompt.text() + kbChar.text())
        self.kbEditPrompt.repaint()
    
    def fcnKbErase(self):
        self.kbEditPrompt.setText(self.kbEditPrompt.text()[:-1])
        self.kbEditPrompt.repaint()
    
    def fcnKbSpace(self):
        self.kbEditPrompt.setText(self.kbEditPrompt.text() + ' ')
        self.kbEditPrompt.repaint()
    
    def fcnKbDash(self):
        self.kbEditPrompt.setText(self.kbEditPrompt.text() + '-')
        self.kbEditPrompt.repaint()

    def fcnKbMark(self):
        self.kbEditPrompt.setText(self.kbEditPrompt.text() + '-')
        self.kbEditPrompt.repaint()
    
    def fcnKbDone(self):
        if type(self.kbTarget) == QLineEdit:
            self.kbTarget.setText(self.kbEditPrompt.text())
        elif type(self.kbTarget) == QPlainTextEdit:
            self.kbTarget.setPlainText(self.kbEditPrompt.text())

        self.kbTarget.repaint()
        self.stackedWidget.setCurrentWidget(self.kbLastPage)

    
    def deleteLevel(self):
        # Check if a category is selected
        selectedCategory = self.listCategories.currentItem()
        if selectedCategory is None:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please select a category.")
            msg.exec_()
            return
        
        # Check if a level is selected
        selectedLevel = self.listLevels.currentItem()
        if selectedLevel is None:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please select a level.")
            msg.exec_()
            return
        
        # Confirm
        msg = QMessageBox()
        msg.setWindowTitle("Confirm")
        msg.setText("All images under this level will be deleted. Are you sure you want to delete this level?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        response = msg.exec_()

        if response != QMessageBox.Yes:
            return
        
        # Delete the level
        category = selectedCategory.text()
        level = selectedLevel.text()

        # Delete the directory
        shutil.rmtree(os.path.join(self.databasePath, category, level))

        # Refresh the manage page
        self.refreshManageLevels()

        # Show success message
        msg = QMessageBox()
        msg.setWindowTitle("Success")
        msg.setText("Level deleted successfully.")
        msg.exec_()

    def addLevel(self):
        # Check if a category is selected
        selectedCategory = self.listCategories.currentItem()
        if selectedCategory is None:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please select a category.")
            msg.exec_()
            return
        
        newLevel = self.editNewLevel.text().strip()

        # Validate
        # - Check if the name is empty
        if len(newLevel) == 0:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please enter a name.")
            msg.exec_()
            return

        # - Check if period or comma is in the name
        if ('.' in newLevel) or (',' in newLevel):
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Periods and commas are not allowed.")
            msg.exec_()
            return
        
        # - Check if the name already exists
        category = selectedCategory.text()
        if newLevel in os.listdir(os.path.join(self.databasePath, category)):
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Level already exists.")
            msg.exec_()
            return
        
        # Create the directory
        os.makedirs(os.path.join(self.databasePath, category, newLevel), exist_ok=True)

        # Refresh the manage page
        self.refreshManageLevels()

        # Clear the input field
        self.editNewLevel.clear()

        # Show success message
        msg = QMessageBox()
        msg.setWindowTitle("Success")
        msg.setText("Level added successfully.")
        msg.exec_()


    def deleteCategory(self):
        # Check if a category is selected
        selectedCategory = self.listCategories.currentItem()
        if selectedCategory is None:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please select a category.")
            msg.exec_()
            return
        
        # Confirm
        msg = QMessageBox()
        msg.setWindowTitle("Confirm")
        msg.setText("All levels and images under this category will be deleted. Are you sure you want to delete this category?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        response = msg.exec_()

        if response != QMessageBox.Yes:
            return
        
        # Delete the category
        category = selectedCategory.text()

        # Delete the directory
        shutil.rmtree(os.path.join(self.databasePath, category))

        # Refresh the manage page
        self.refreshManageCategories()

        # Show success message
        msg = QMessageBox()
        msg.setWindowTitle("Success")
        msg.setText("Category deleted successfully.")
        msg.exec_()


    def addCategory(self):
        newCategory = self.editNewCategory.text().strip()

        # Validate
        # - Check if the name is empty
        if len(newCategory) == 0:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please enter a name.")
            msg.exec_()
            return

        # - Check if period or comma is in the name
        if ('.' in newCategory) or (',' in newCategory):
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Periods and commas are not allowed.")
            msg.exec_()
            return
        
        # - Check if the name already exists
        if newCategory in os.listdir(self.databasePath):
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Category already exists.")
            msg.exec_()
            return
        
        # Create the directory
        os.makedirs(os.path.join(self.databasePath, newCategory), exist_ok=True)

        # Refresh the manage page
        self.refreshManageCategories()

        # Clear the input field
        self.editNewCategory.clear()

        # Show success message
        msg = QMessageBox()
        msg.setWindowTitle("Success")
        msg.setText("Category added successfully.")
        msg.exec_()

    def addDrawing(self):
        # Get the image name
        imageName = self.editNewDrawing.text().strip()

        # Validate
        # - Check if the name is empty
        if len(imageName) == 0:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please enter a name.")
            msg.exec_()
            return
        
        # - Check if period or comma is in the name
        if ('.' in imageName) or (',' in imageName):
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Periods and commas are not allowed.")
            msg.exec_()
            return
        
        selectedCategory = self.listCategories.currentItem()
        selectedLevel = self.listLevels.currentItem()
        
        if selectedCategory is None or selectedLevel is None:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please select a category and a level.")
            msg.exec_()
            return
        
        category = selectedCategory.text()
        level = selectedLevel.text()

        # Check if the name already exists
        if imageName + '.jpg' in os.listdir(os.path.join(self.databasePath, category, level)):
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Image already exists.")
            msg.exec_()
            return

        # Open dialog to select image file
        fileDialog = QFileDialog()
        fileDialog.setFileMode(QFileDialog.ExistingFiles)
        fileDialog.setNameFilter("Images (*.jpg)")
        if not fileDialog.exec_():
            return
        
        files = fileDialog.selectedFiles()

        # Open dialog to select mp3 file
        fileDialog = QFileDialog()
        fileDialog.setFileMode(QFileDialog.ExistingFiles)
        fileDialog.setNameFilter("Audio (*.mp3)")
        if not fileDialog.exec_():
            return
        
        mp3Files = fileDialog.selectedFiles()
        

        for file in files:
            # Copy the file to the database
            shutil.copy(file, os.path.join(self.databasePath, category, level, imageName + '.jpg'))
        
        for mp3File in mp3Files:
            # Copy the file to the database
            shutil.copy(mp3File, os.path.join(self.databasePath, category, level, imageName + '.mp3'))

        # Refresh the manage page
        self.refreshManageImages()

        # Clear the input field
        self.editNewDrawing.clear()

        # Show success message
        msg = QMessageBox()
        msg.setWindowTitle("Success")
        msg.setText("Image(s) added successfully.")
        msg.exec_()
        

    def deleteDrawing(self):
        # Check if a category is selected
        selectedCategory = self.listCategories.currentItem()
        selectedLevel = self.listLevels.currentItem()
        selectedImage = self.listImages.currentItem()
        if selectedCategory is None or selectedLevel is None or selectedImage is None:
            msg = QMessageBox()
            msg.setWindowTitle("Error")
            msg.setText("Please select a category, a level and an image.")
            msg.exec_()
            return
        
        # Confirm
        msg = QMessageBox()
        msg.setWindowTitle("Confirm")
        msg.setText("Are you sure you want to delete this image?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        response = msg.exec_()

        if response != QMessageBox.Yes:
            return
        
        # Delete the image
        category = selectedCategory.text()
        level = selectedLevel.text()
        image = selectedImage.text()

        # Delete the file
        os.remove(os.path.join(self.databasePath, category, level, image + '.jpg'))

        # Refresh the manage page
        self.refreshManageImages()

        # Show success message
        msg = QMessageBox()
        msg.setWindowTitle("Success")
        msg.setText("Image deleted successfully.")
        msg.exec_()

    def refreshManageCategories(self):
            
        # Unselect the selected items
        self.listCategories.clearSelection()
        self.listLevels.clearSelection()
        self.listImages.clearSelection()

        # Clear the list of levels
        self.listLevels.clear()

        # Clear the list of images
        self.listImages.clear()

        # Clear instructions
        self.editInstructions.setPlainText('')

        listOfCategories = os.listdir(self.databasePath)

        # Sort the list of categories in ascending order
        listOfCategories.sort()

        # Populate the list of categories
        self.listCategories.clear()
        for category in listOfCategories:
            self.listCategories.addItem(category)

        

        


    def refreshManageLevels(self):

        # Unselect the selected items
        self.listLevels.clearSelection()
        self.listImages.clearSelection()
        self.showWhiteImageOnDrawingPreview()

        # Clear the list of images
        self.listImages.clear()
        # Clear instructions
        self.editInstructions.setPlainText('')

        selectedCategory = self.listCategories.currentItem()
        if selectedCategory is None:
            return

        category = selectedCategory.text()

        try:
            listOfLevels = os.listdir(os.path.join(self.databasePath, category))
            # Sort
            listOfLevels.sort()
        except:
            return

        # Populate the list of levels
        self.listLevels.clear()
        for level in listOfLevels:
            self.listLevels.addItem(level)

        

        
    

    def refreshManageImages(self):

        # Unselect the selected items
        self.listImages.clearSelection()
        self.showWhiteImageOnDrawingPreview()

        selectedCategory = self.listCategories.currentItem()
        selectedLevel = self.listLevels.currentItem()

        if selectedCategory is None or selectedLevel is None:
            return

        category = selectedCategory.text()
        level = selectedLevel.text()
        
        try:
            # Get the list of jpg images in the directory
            listOfImages = [f[0:-4] for f in os.listdir(os.path.join(self.databasePath, category, level)) if f.endswith('.jpg')]
            # Sort
            listOfImages.sort()
        except:
            return

        # Populate the list of images
        self.listImages.clear()
        for image in listOfImages:
            self.listImages.addItem(image)

        if not os.path.exists(os.path.join(self.databasePath, category, level, 'instructions.txt')):
            with open(os.path.join(self.databasePath, category, level, 'instructions.txt'), 'w') as f:
                f.write('')
        
        with open(os.path.join(self.databasePath, category, level, 'instructions.txt'), 'r') as f:
            instructions = f.read()
        
        self.editInstructions.setPlainText(instructions)
    

    def manageShowImage(self):
        selectedCategory = self.listCategories.currentItem()
        selectedLevel = self.listLevels.currentItem()
        selectedImage = self.listImages.currentItem()

        if selectedCategory is None or selectedLevel is None or selectedImage is None:
            self.showWhiteImageOnDrawingPreview()
            return

        category = selectedCategory.text()
        level = selectedLevel.text()
        image = selectedImage.text()

        if not os.path.exists(os.path.join(self.databasePath, category, level, image + '.jpg')):
            self.showWhiteImageOnDrawingPreview()
            return

        img = cv2.imread(os.path.join(self.databasePath, category, level, image + '.jpg'))

        self.showCVImage(img, self.lblPreviewDrawing)

    
    def showWhiteImageOnDrawingPreview(self):
        blankImage = np.ones((self.lblPreviewDrawing.height(), self.lblPreviewDrawing.width(), 3), np.uint8) * 255
        self.showCVImage(blankImage, self.lblPreviewDrawing)

    def saveInstructions(self):
        selectedCategory = self.listCategories.currentItem()
        selectedLevel = self.listLevels.currentItem()

        if selectedCategory is None or selectedLevel is None:
            return

        category = selectedCategory.text()
        level = selectedLevel.text()

        with open(os.path.join(self.databasePath, category, level, 'instructions.txt'), 'w') as f:
            f.write(self.editInstructions.toPlainText())

        msg = QMessageBox()
        msg.setWindowTitle("Success")
        msg.setText("Instructions saved successfully.")
        msg.exec_()
    

    def refreshSelectLevels(self):
        # Clear the lists
        self.listSelectDrawing.clear()
        self.listSelectLevel.clear()

        # Unselect the selected items
        # self.listSelectCategory.clearSelection()
        self.listSelectLevel.clearSelection()

        selectedCategory = self.listSelectCategory.currentItem()

        if selectedCategory is None:
            return
        
        category = selectedCategory.text()

        listOfLevels = os.listdir(os.path.join(self.databasePath, category))
        # Sort
        listOfLevels.sort()

        # Populate the list of levels
        self.listSelectLevel.clear()

        for level in listOfLevels:
            self.listSelectLevel.addItem(level)

    def refreshSelectImages(self):
        selectedCategory = self.listSelectCategory.currentItem()
        selectedLevel = self.listSelectLevel.currentItem()

        if selectedLevel is None or selectedCategory is None:
            return
        
        category = selectedCategory.text()
        level = selectedLevel.text()

        # Get the list of jpg images in the directory
        try:
            listOfImages = [f for f in os.listdir(os.path.join(self.databasePath, category, level)) if f.endswith('.jpg')]
            # Sort
            listOfImages.sort()
        except:
            return

        # Unselect the selected items
        self.listSelectDrawing.clearSelection()
        # Populate the list of images
        self.listSelectDrawing.clear()

        for image in listOfImages:
            prepend = ''
            userDirectory = os.path.join(self.usersPath, self.currentUser, category, level)
            if os.path.exists(os.path.join(userDirectory, image[0:-4] + '.txt')):
                prepend = '✓ '
            self.listSelectDrawing.addItem(prepend + image[0:-4])
    
    def selectProceed(self):
        selectedCategory = self.listSelectCategory.currentItem()
        selectedLevel = self.listSelectLevel.currentItem()
        selectedImage = self.listSelectDrawing.currentItem()

        if selectedCategory is None or selectedLevel is None or selectedImage is None:
            return
        
        category = selectedCategory.text()
        level = selectedLevel.text()
        image = selectedImage.text()

        self.currentCategory = category
        self.currentLevel = level
        if image.startswith('✓'):
            self.currentImage = image[2:]
        else:
            self.currentImage = image

        # Load instructions
        with open(os.path.join(self.databasePath, category, level, 'instructions.txt'), 'r') as f:
            instructions = f.read()
        
        # Display instructions
        self.lblInstructions.setText(instructions)

        # Show the page
        self.stackedWidget.setCurrentWidget(self.pgInstructions)
    

    def startDrawing(self):
        selectedCategory = self.listSelectCategory.currentItem()
        selectedLevel = self.listSelectLevel.currentItem()
        selectedImage = self.listSelectDrawing.currentItem()

        if selectedCategory is None or selectedLevel is None or selectedImage is None:
            return

        self.resetDrawingArea()

        img = cv2.imread(os.path.join(self.databasePath, self.currentCategory, self.currentLevel, self.currentImage + '.jpg'))

        # Resize the image to the size of the label
        img = cv2.resize(img, (self.drawingArea.width(), self.drawingArea.height()))

        # Convert the image to pure black and white
        img[img < 128] = 0
        img[img >= 128] = 255

        # Set the current drawing
        self.currentDrawing = img.copy()

        # Make a copy of the current drawing
        self.combinedImage = self.currentDrawing.copy()

        # Lighten the black pixels to light gray
        self.combinedImage[self.combinedImage == 0] = self.grayValue

        # Display the image on the label
        self.displayImage()

        # Set the tool to pencil
        self.setToolToPencil()

        self.stackedWidget.setCurrentWidget(self.pgDraw)
    
    def backFromDrawing(self):
        self.showLevelSelectionPage()

    def continueAfterSuccess(self, score):
        # Find the current row based from the current image
        currentIndex = -1
        for i in range(self.listSelectDrawing.count()):
            item = self.listSelectDrawing.item(i)
            currentText = item.text() if not item.text().startswith('✓') else item.text()[2:]
            if currentText == self.currentImage:
                currentIndex = i
                break

        next_item = self.listSelectDrawing.item(currentIndex + 1) if currentIndex + 1 < self.listSelectDrawing.count() else None

        if next_item is None:
            self.showLevelSelectionPage()
            return
        
        print("Current index:", currentIndex)
        self.listSelectDrawing.setCurrentItem(next_item)

        print("New index:", self.listSelectDrawing.currentRow())
        self.currentImage = next_item.text() if not next_item.text().startswith('✓') else next_item.text()[2:]

        print("New image:", self.currentImage)

        self.startDrawing()


    def refreshSelectCategories(self):
            
        # Unselect the selected items
        self.listSelectCategory.clearSelection()
        self.listSelectLevel.clearSelection()
        self.listSelectDrawing.clearSelection()

        # Clear the list of levels
        self.listSelectLevel.clear()

        # Clear the list of images
        self.listSelectDrawing.clear()

        listOfCategories = os.listdir(self.databasePath)
        # Sort
        listOfCategories.sort()

        # Populate the list of categories
        self.listSelectCategory.clear()
        for category in listOfCategories:
            self.listSelectCategory.addItem(category)


    def shutDown(self):
        # Confirm
        msg = QMessageBox()
        msg.setWindowTitle("Confirm")
        msg.setText("Are you sure you want to shut down the system?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        response = msg.exec_()
        if response != QMessageBox.Yes:
            return
        
        if OS == OS_LINUX:
            os.system("sudo shutdown -h now")
        else:
            print("SHUT DOWN...")


# Main function
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()

    if OS == OS_LINUX:
        window.showFullScreen()
    else:
        window.show()
    sys.exit(app.exec_())