# Dependencies
import RPi.GPIO as GPIO
import Constants as const
import LiquidCrystalDisplay
import requests
import urllib2
import sqlite3
import string
import random
import json
import os

from picamera import PiCamera
from pad4pi import rpi_gpio
from hx711 import HX711
from time import sleep

# Connection to database (Sqlite 3)
conn = sqlite3.connect('/home/pi/application/mainapp.db')
c = conn.cursor()

# 16 x 2 LCD
display = LiquidCrystalDisplay.lcd()

# 4 x 3 keypad
keypadFactory = rpi_gpio.KeypadFactory()
keypad = keypadFactory.create_4_by_3_keypad()

# Pi camera
camera = PiCamera()
camera.rotation = 180

# Storage load cell
storageHx = HX711(21, 20)

# Bottle load cell
bottleHx = HX711(9, 10)

# Application Setup
def setup():
    print("Setup start")
    global GPIO
    GPIO.setmode(GPIO.BCM)
    
    print("Setting up option buttons")
    # Button GPIO setup
    GPIO.setup(const.SELECTION_BUTTONS, GPIO.IN, pull_up_down = GPIO.PUD_UP)

    print("Setting up coin hopper")
    # Coin Hopper GPIO setup
    GPIO.setup(const.COIN_COUNTER, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    GPIO.add_event_detect(const.COIN_COUNTER, GPIO.FALLING, bouncetime=180)

    print("Setting up relays")
    # Relay (Coin Hopper) GPIO setup
    GPIO.setup(const.COIN_HOPPER, GPIO.OUT)
    # Relay (Bottle Conveyor) GPIO setup
    GPIO.setup(const.BOTTLE_CONVEYOR, GPIO.OUT)

    print("Setting up LEDs")
    # LEDs GPIO setup
    GPIO.setup(const.RED_LED, GPIO.OUT)
    GPIO.setup(const.YELLOW_LED, GPIO.OUT)
    GPIO.setup(const.GREEN_LED, GPIO.OUT)

    print("Setting default GPIO states")
    # Default GPIO states
    GPIO.output(const.COIN_HOPPER, const.HIGH)
    GPIO.output(const.BOTTLE_CONVEYOR, const.HIGH)
    GPIO.output(const.RED_LED, const.LOW)
    GPIO.output(const.YELLOW_LED, const.LOW)
    GPIO.output(const.GREEN_LED, const.LOW)

    print("Setting up load cells")
    # Storage load cell setup
    storageHx.set_offset(8475410.625)
    storageHx.set_scale(317.949)
    storageHx.tare()
    # Bottle load cell setup
    bottleHx.set_offset(8685773.4375)
    bottleHx.set_scale(306.12)
    bottleHx.tare()

    print("Setup done")

# Application loop
def loop():
    global GPIO
    
    display.lcd_display_string_pos("Smart PET", 1, 3)
    display.lcd_display_string("Bottle Collector", 2)
    ValidateStorageWeight()
    if GreenButtonIsPressed() and RedButtonIsPressed():
        display.lcd_clear()
        display.lcd_display_string_pos("Shut down", 1, 3)
        display.lcd_display_string("Turn off switch", 2)
        ShutDown()
    elif GreenButtonIsPressed() or RedButtonIsPressed():
        sleep(0.3)
        transaction = SelectTransaction()
        if transaction == const.NO_TRANSACTION:
            pass
        elif transaction == const.DEPOSIT_TRANSACTION:
            print("Deposit transaction")
            DepositBottles()
        elif transaction == const.REDEEM_TRANSACTION:
            print("Redeem transacion")
            RedeemCredits()

def ShutDown():
    global GPIO
    GPIO.cleanup()
    os.system("sudo shutdown now")
    
def ValidateStorageWeight():
    while True:
        readings = ReadWeight(storageHx)
        if readings >= const.STORAGE_MAX_WEIGHT:
            display.lcd_clear()
            display.lcd_display_string_pos("Storage full", 1, 2)
            display.lcd_display_string("Collect bottles", 2)
            stillOnMaxStorageWeight = True
            while stillOnMaxStorageWeight:
                TurnOnRedLed()
                readings = ReadWeight(storageHx)
                if (readings < const.STORAGE_MAX_WEIGHT):
                    stillOnMaxStorageWeight = False
                if GreenButtonIsPressed() and RedButtonIsPressed():
                    display.lcd_clear()
                    display.lcd_display_string_pos("Shut down", 1, 3)
                    display.lcd_display_string("Turn off switch", 2)
                    ShutDown()
            display.lcd_clear()
            break
        elif readings >= const.STORAGE_AVERAGE_WEIGHT and readings < const.STORAGE_MAX_WEIGHT:
            TurnOnYellowLed()    
            break
        elif readings < const.STORAGE_AVERAGE_WEIGHT or readings == const.STORAGE_MIN_WEIGHT:
            TurnOnGreenLed()
            break

def TurnOnRedLed():
    GPIO.output(const.RED_LED, const.HIGH)
    GPIO.output(const.YELLOW_LED, const.LOW)
    GPIO.output(const.GREEN_LED, const.LOW)

def TurnOnYellowLed():
    GPIO.output(const.RED_LED, const.LOW)
    GPIO.output(const.YELLOW_LED, const.HIGH)
    GPIO.output(const.GREEN_LED, const.LOW)

def TurnOnGreenLed():
    GPIO.output(const.RED_LED, const.LOW)
    GPIO.output(const.YELLOW_LED, const.LOW)
    GPIO.output(const.GREEN_LED, const.HIGH)

def ReadWeight(weightSensor):
    readings = weightSensor.get_grams()
    weightSensor.power_down()
    sleep(.001)
    weightSensor.power_up()
    
    if readings < 0:
        readings = 0
    return readings

def GreenButtonIsPressed():
    return not(GPIO.input(const.GREEN_BUTTON))

def RedButtonIsPressed():
    return not(GPIO.input(const.RED_BUTTON))

def SelectTransaction():
    time = 5
    transaction = 0
    display.lcd_clear()
    display.lcd_display_string("G:Deposit bottle", 1)
    display.lcd_display_string("R:Redeem credits", 2)
    sleep(0.3)
    
    while time > 0:
        if GreenButtonIsPressed():
            sleep(0.3)
            transaction = const.DEPOSIT_TRANSACTION
            break
        if RedButtonIsPressed():
            sleep(0.3)
            transaction = const.REDEEM_TRANSACTION
            break
        sleep(1)
        time -= 1
    
    display.lcd_clear()
    return transaction

# Generates 11 digits string account number
def GenerateAccountNumber():
    return ''.join(random.choice(string.digits) for i in range(11))

# Creates a new account
def CreateAccount():
    accountIsValid = False

    display.lcd_clear()
    display.lcd_display_string("Creating your", 1)
    display.lcd_display_string("account number", 2)

    while not accountIsValid:
        accountNumber = GenerateAccountNumber()
        accountIsValid = ValidateAccountNumber(accountNumber)
        if accountIsValid:
            credit = 0.00
            c.execute('INSERT INTO Accounts VALUES(?, ?);', (accountNumber, credit))
            conn.commit()
    sleep(1)
    display.lcd_clear()
    DisplayAccountNumber(accountNumber, 11)
    return accountNumber

def DisplayAccountNumber(accountNumber, timeOfDisplay):
    time = timeOfDisplay
    toStopDisplay = False
    display.lcd_clear()

    while True:
        display.lcd_display_string("New account no.:", 1)
        display.lcd_display_string(accountNumber, 2)
        sleep(1)

        if time == 0:
            display.lcd_clear()
            display.lcd_display_string("Do you need more", 1)
            display.lcd_display_string("time? G:Yes R:No", 2)
            while True:
                if GPIO.input(const.GREEN_BUTTON) == False:
                    display.lcd_clear()
                    time = timeOfDisplay
                    break
                if GPIO.input(const.RED_BUTTON) == False:
                    display.lcd_clear()
                    toStopDisplay = True
                    break

        if toStopDisplay:
            break

        time = time - 1
    display.lcd_clear()
    sleep(0.2)

def ValidateAccountNumber(accountNumber):
    c.execute('SELECT AccountNumber FROM Accounts WHERE AccountNumber = ?;', (accountNumber,))
    existingAccountNumber = c.fetchone()
    if existingAccountNumber is None:
        return True
    return False

def UpdateAccount(accountNumber, newCredit):
    c.execute('UPDATE Accounts SET Credits = ? WHERE AccountNumber = ?;',(newCredit, accountNumber))
    conn.commit()

def GetAccountCredit(accountNumber):
    c.execute('SELECT Credits FROM Accounts WHERE AccountNumber = ?;', (accountNumber,))
    credit = c.fetchone()[0]
    return credit

def ShowAccountDetails(accountNumber):
    display.lcd_clear()
    display.lcd_display_string("A#: " + accountNumber, 1)
    display.lcd_display_string("Credits: " + str(GetAccountCredit(accountNumber)), 2)
    sleep(5)
    display.lcd_clear()

# Deposit transaction
def DepositBottles():
    display.lcd_clear()
    display.lcd_display_string("Transaction:", 1)
    display.lcd_display_string("Deposit bottles", 2)
    sleep(3)
    accountNumber = GetAccountNumber()
    if accountNumber != "":
        ShowAccountDetails(accountNumber)
        inProcess = True
        bottleCount = 0
        totalAmount = 0
        while inProcess:
            display.lcd_clear()
            display.lcd_display_string_pos("Insert bottles", 1, 1)
            display.lcd_display_string("R: Cancel", 2)
            redIsButtonPressed = False
            readings = ReadWeight(bottleHx)
            checkingWeight = True

            while checkingWeight:
                if readings > 1:
                    checkingWeight = False
                elif RedButtonIsPressed():
                    sleep(0.3)
                    display.lcd_clear()
                    inProcess = False
                    checkingWeight = False
                    redIsButtonPressed = True
                    break
                readings = ReadWeight(bottleHx)
            if redIsButtonPressed:
                break
            sleep(0.3)
            if readings <= const.BOTTLE_VALID_WEIGHT and readings != const.BOTTLE_CONVEYOR_EMPTY:
                display.lcd_clear()
                display.lcd_display_string("Processing image", 1)
                display.lcd_display_string("Please wait ...", 2)
                print("Image Processing started")
                CaptureImage()
                ImageProcess()
                objectIsBottle = GetImageProcessResult()
                print("Image Processing ended")
                if objectIsBottle:
                    RunConveyor()
                    creditAmount = CalculateDepositCredits(readings)
                    AddBottleCredits(accountNumber, creditAmount)
                    bottleCount += 1
                    totalAmount += creditAmount
                else:
                    inProcess = InvalidObject()
            else:
                inProcess = InvalidObject()
        display.lcd_clear()
        display.lcd_display_string("Count:", 1)
        display.lcd_display_string("Total:", 2)
        display.lcd_display_string_pos(str(bottleCount), 1, 13)
        display.lcd_display_string_pos(str(totalAmount), 2, 12)
        sleep(3)
        display.lcd_clear()
        print("Deposit Bottles with account number: " + accountNumber)
    else:
        AccountDoesNotExist()

def AccountDoesNotExist():
    display.lcd_clear()
    display.lcd_display_string_pos("Account does", 1, 2)
    display.lcd_display_string_pos("not exist!", 2, 3)
    sleep(3)
    display.lcd_clear()

def InvalidObject():
    display.lcd_clear()
    display.lcd_display_string("Invalid object", 1)
    display.lcd_display_string_pos("Try again?", 2, 2)
    decision = False
    deciding = True
    while deciding:
        if GreenButtonIsPressed():
            decision = True
            deciding = False
        if RedButtonIsPressed():
            decision = False
            deciding = False
    return decision

def CaptureImage():
    os.remove('/home/pi/application/ImageToSend/image.jpg')
    camera.start_preview()
    sleep(3)
    camera.capture('/home/pi/application/ImageToSend/image.jpg')
    camera.stop_preview()

def GetImageProcessResult():
    c.execute('SELECT Result FROM ImageProcess;')
    result = c.fetchone()[0]
    if str(result) == "1":
        return True
    return False

def ImageProcess():
    os.system("python3 /home/pi/application/imageprocess/scripts/label_image.py")

def CalculateDepositCredits(bottleWeight):
    credits = (bottleWeight * const.BOTTLE_PRICE_PER_KILO) / const.BOTTLE_WEIGHT_SCALE
    return float("{0:.2f}".format(credits))

def ValidateBottleWeight(bottleWeight):
    if bottleWeight <= const.BOTTLE_VALID_WEIGHT:
        return True
    return False

def RunConveyor():
    GPIO.output(const.BOTTLE_CONVEYOR, const.LOW)
    sleep(5)
    GPIO.output(const.BOTTLE_CONVEYOR, const.HIGH)

def AddBottleCredits(accountNumber, amount):
    accountCredits = GetAccountCredit(accountNumber)
    newCredit = float("{0:.2f}".format(accountCredits)) + float("{0:.2f}".format(amount)) 
    UpdateAccount(accountNumber, str(newCredit))

# Redeem transaction
def RedeemCredits():
    display.lcd_clear()
    display.lcd_display_string("Transaction:", 1)
    display.lcd_display_string("Redeem credits", 2)
    sleep(3)
    accountNumber = InputAccountNumber()

    if accountNumber != "":
        ShowAccountDetails(accountNumber)
        tryAgain = True
        onTransaction = True
        while onTransaction:
            if tryAgain:
                amount = GetAmountToRedeem()
                amountIsValid = ValidateAmount(accountNumber, amount)
                if amountIsValid:
                    DispenseCoin(int(amount))
                    DeductDispensedCoin(accountNumber, amount)
                    display.lcd_clear()
                    display.lcd_display_string_pos("Thank you", 1, 3)
                    display.lcd_display_string("Save the planet", 2)
                    sleep(2)
                    display.lcd_clear()
                    onTransaction = False
                else:
                    display.lcd_clear()
                    display.lcd_display_string("Invalid amount", 1)
                    display.lcd_display_string("Try again?", 2)
                    sleep(2)
                    deciding = True
                    while deciding:
                        if GreenButtonIsPressed():
                            deciding = False
                            tryAgain = True
                            display.lcd_clear()
                            sleep(0.3)
                        elif RedButtonIsPressed():
                            tryAgain = False
                            onTransaction = False
                            deciding = False
                            display.lcd_clear()
                            sleep(0.3)
    else:
        AccountDoesNotExist()

def DeductDispensedCoin(accountNumber, amount):
    accountCredits = GetAccountCredit(accountNumber)
    newCredit = int(accountCredits) - int(amount)
    UpdateAccount(accountNumber, str(newCredit))

def GetAmountToRedeem():
    amount = ""
    done = False

    display.lcd_clear()
    display.lcd_display_string("Enter amount: ", 1)

    while not done:
        keyCharacter = keypad.getKey()

        if keyCharacter is not None:
            sleep(0.3)
            amount = amount + str(keyCharacter)

        display.lcd_display_string(amount, 2)

        if GreenButtonIsPressed():
            done = True
            sleep(0.3)
        if RedButtonIsPressed():
            done = True
            amount = "0"
            sleep(0.3)

    return amount

def DispenseCoin(amount):
    coinCount = 0
    while(coinCount != amount):
        GPIO.output(const.COIN_HOPPER, const.LOW)
        if GPIO.event_detected(const.COIN_COUNTER):
            coinCount += 1
    GPIO.output(const.COIN_HOPPER, const.HIGH)

def ValidateAmount(accountNumber, amount):
    accountCredits = GetAccountCredit(accountNumber)
    if int(amount) > int(accountCredits):
        return False
    return True

def GetExistingAccountNumber():
    accountNumberSize = 11
    accountNumber = ""

    display.lcd_clear()
    display.lcd_display_string("Enter account:", 1)
        
    while accountNumberSize != 0 :
        keyCharacter = keypad.getKey()
        if keyCharacter is not None:
            sleep(0.3)
            accountNumber = accountNumber + str(keyCharacter)
            accountNumberSize -= 1

        display.lcd_display_string(accountNumber, 2)
    
    return accountNumber

def InputAccountNumber():
    accountNumber = ""
    tries = 3
    while tries != 0:
        accountNumber = GetExistingAccountNumber()
        if not(ValidateAccountNumber(accountNumber)):
            break
        display.lcd_clear()
        display.lcd_display_string("Invalid account!", 1)
        sleep(1)
        display.lcd_clear()
        accountNumber = ""
        tries -= 1

    return accountNumber

def GetAccountNumber():
    accountNumber = ""
    option = const.CREATE_ACCOUNT

    display.lcd_clear()
    display.lcd_display_string("G:Enter account", 1)
    display.lcd_display_string("R:Create account", 2)

    while True:
        if GreenButtonIsPressed():
            option = const.ENTER_ACCOUNT_NUMBER
            break

        if RedButtonIsPressed():
            option = const.CREATE_ACCOUNT
            break

    if option == const.ENTER_ACCOUNT_NUMBER:
        accountNumber = InputAccountNumber()
    elif option == const.CREATE_ACCOUNT:
        accountNumber = CreateAccount()

    display.lcd_clear()

    return accountNumber

# Main application
try:
    setup()
    while True:
        loop()
except KeyboardInterrupt:
    GPIO.cleanup()
finally:
    GPIO.cleanup()