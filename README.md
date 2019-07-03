# Smart PET Bottle Collector

  The **Smart Pet Bottle Collector** is a simple application of image processing using Tensorflow powered by Raspberry Pi 3 Model B+ written in Python 2.7 and Python 3.6 with account and rewarding system.

# Project Description
  There are two main transaction on this system, deposit bottles and redeem credits. Deposit bottles transaction will require a user with an existing account else the system will create an eleven digit account number that the user will use through his/her transactions. This account number will be used to validate and allow the user to deposit bottles on the machine. Upon bottle deposit transaction the system will check for the weight of an object to validate the object's weight then check if the object is a PET bottle by image processing (I retrained mobilenet_v1_0.50_224 model with Tensorflow). Finally if the object is a bottle, the system will activate the conveyor, calculate the equivalent credit for the bottle and add the credit to the user's account. Redeem credits transaction will require the user a valid account number, when the user input his/her account number on the system, the system will show the user's account number and remaining credits. The user can withdraw the balance credits by encoding the desired amount then the coin hopper will count the equivalent coin credits being withdrawn. The system also checks and updates the status of the bottle storage stopping any transactions when the storage is full

### Block Diagram
![Block Diagram](https://user-images.githubusercontent.com/22982449/55237395-0e84ae00-526d-11e9-9241-67205b6e64e1.png)

### References
• https://www.tensorflow.org/<br/>
• https://codelabs.developers.google.com/codelabs/tensorflow-for-poets/#0
