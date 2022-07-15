import asyncio
import json
from pprint import pprint
import random
import time
import pandas as pd

import aiohttp
from fake_useragent import UserAgent
from tqdm import tqdm

class AutodocParser:
    def __init__(self, data):
        self.ouputFilename = "catalog_output.xlsx"
        self.timeout = 5
        self.sessionTimeout = aiohttp.ClientTimeout(total=None, sock_connect=self.timeout, sock_read=self.timeout)
        self.connector = aiohttp.TCPConnector(ssl=False, limit=10000)
        self.data = data
        self.userAgent = UserAgent().random
        self.headers = {}

        self.ouputFilename = "details_output.xlsx"
        self.loginAttempts = ["DC1/O1127x9ZL4GU2bhQgg==", "W7F+x+sPZUPsCAcXwYSH5Q=="]        
        
        self.accounts = self.readAccountsFile()
        self.accountsOld = [
            {
                "login": "KNG-16191",
                "password": "gera1905"
            },
            {
                "login": "KNG-16078",
                "password": "6sqqSZ77PHZPmEL"
            },
            {
                "login": "KLD-32227",
                "password": "kjqwhekljqhw"
            },
            {
                "login": "KNG-16206",
                "password": "asdasdasd"
            },
            {
                "login": "KLD-32228",
                "password": "qweqweqwe"
            },
        ]

        self.account = self.accounts[0]


    async def startParsing(self):
        challengeGuid = await self.getChallengeGuid()
        tokenData = await self.getToken()
        self.headers = {
            "authorization": tokenData["token_type"] + " " + tokenData["access_token"],
            "user-agent": self.userAgent
        }
        loginData = await self.getLoginData(challengeGuid, random.choice(self.loginAttempts))
        session = loginData["session"]
        if loginData["response"]["clientStatus"] != 0:
            await self.startParsing()
            return
        # profileData = await self.getProfileData()

        outputItems = []
        # Проход по номерам деталей
        for detailData in tqdm(self.data):
            detailName = detailData["detailName"]
            detailNumber = detailData["detailNumber"]
            manufacturers = await self.getManufacturerInfo(detailNumber.replace("-", ""), session)
            
            # Проход по номерам производителей для каждой детали
            for manufacturer in manufacturers:
                manufacturerID = manufacturer["id"]
                manufacturerName = manufacturer["manufacturerName"]
                partName = manufacturer["partName"]
                partNumber = manufacturer["artNumber"]

                #* Вся инфа о детали
                detailInfo = await self.getDetailInfo(session, manufacturerID, partNumber)
                originalDetails = detailInfo["originals"]
                analogDetails = detailInfo["analogs"]

                

                #* Оригиналы
                for item in originalDetails["inventoryItems"]:
                    outputDetailData = {
                        "type": "original",
                        "detailName": detailName,
                        "detailNumber": detailNumber,
                        "deliveryDays": item["deliveryDays"],
                        "minimumDeliveryDays": item["minimalDeliveryDays"],
                        "manufacturerName": manufacturerName,
                        "price": item["price"],
                        "supplier": item["supplier"]["name"] # Поставщик
                    }
                    outputItems.append(outputDetailData)

                # #* Аналоги из запроса на оригинал
                # for item in originalDetails["analogs"]:
                #     outputDetailData = {
                #         "type": "analogFromOriginal",
                #         "detailName": item["name"],
                #         "detailNumber": item["partNumber"],
                #         "deliveryDays": item["inventoryItems"][0]["deliveryDays"],
                #         "minimumDeliveryDays": item["inventoryItems"][0]["minimalDeliveryDays"],
                #         "manufacturerName": item["manufacturer"]["name"],
                #         "price": item["inventoryItems"][0]["price"],
                #         "supplier": item["inventoryItems"][0]["supplier"]["name"] # Поставщик
                #     }
                #     outputItems.append(outputDetailData)

                #* Аналоги
                for item in analogDetails["analogs"]:
                    outputDetailData = {
                        "type": "analog",
                        "detailName": item["name"],
                        "detailNumber": item["partNumber"], # можно использовать displayPartNumber
                        # "deliveryDays": item["deliveryDays"],
                        "minimumDeliveryDays": item["minimalDeliveryDays"],
                        "manufacturerName": item["manufacturer"]["name"],
                        "price": item["minimalPrice"],
                        # "supplier": item["inventoryItems"][0]["supplier"]["name"] # Поставщик
                    }
                    outputItems.append(outputDetailData)


                # log(f"examples/originals/original_{detailNumber}_{manufacturerID}.json", originalDetails)
                # log(f"examples/analogs/analog_{detailNumber}_{manufacturerID}.json", analogDetails)
            # hash = await self.getHash()

        await session.close()

        self.writeToExcel(outputItems)




    async def getDetailInfo(self, session, manufacturerID, detailNumber):
        originalsUrl = f"https://webapi.autodoc.ru/api/spareparts/{manufacturerID}/{detailNumber}/2?framesId=undefined&attempt=undefined&isrecross=false"
        analogsUrl = f"https://webapi.autodoc.ru/api/spareparts/analogs/{manufacturerID}/{detailNumber}/2"
        session.headers["hash_"] = await self.getHash(manufacturerID, detailNumber)       
        session.headers["dnt"] = "1"       
        session.headers["source_"] = "Site2"       
        
        # original
        originalsResponse = await session.get(originalsUrl)
        originalsResponseJson = await originalsResponse.json()

        # analogs
        analogsResponse = await session.get(analogsUrl)
        analogsResponseJson = await analogsResponse.json()

        returnData = {
            "originals": originalsResponseJson,
            "analogs": analogsResponseJson
        }

        return returnData


    async def getManufacturerInfo(self, partNumber, session):
        url = f"https://webapi.autodoc.ru/api/manufacturers/{partNumber}?showAll=false"
        response = await session.get(url)
        responseJson = await response.json()
        return responseJson

    
    async def getProfileData(self):
        url = "https://webapi.autodoc.ru/api/client/profile"
        async with aiohttp.request("GET", url) as response:
            responseJson = await response.json()
        return responseJson


    async def getLoginData(self, challengeGuid, attempt):
        url = "https://webapi.autodoc.ru/api/account/login"
        
        data = {
            "attempt": attempt,
            "challengeGuid": challengeGuid,
            "gRecaptchaResponse": "",
            "login": self.account["login"],
            "password": self.account["password"],
            "rememberMe": "true"
        }

        session = aiohttp.ClientSession(connector=self.connector, headers=self.headers)
        response = await session.post(url, data=data)
        responseJson = await response.json()
        returnData = {
            "response": responseJson,
            "session": session
        }
        
        return returnData


    async def createSession(self, authData, hash) -> aiohttp.ClientSession:
        headers = {
            "user-agent": self.userAgent,
            "authorization": authData["token_type"] + " " + authData["access_token"],
            "hash": hash
        }
        session = aiohttp.ClientSession(connector=self.connector, timeout=self.sessionTimeout, headers=headers)
        return session


    #! Тут может вылезти капча
    async def getChallengeGuid(self):
        url = "https://webapi.autodoc.ru/api/captha?resource=Auth"
        async with aiohttp.request("GET", url) as response:
            responseJson = await response.json()
            challengeGuid = responseJson["challengeGuid"]
        return challengeGuid


    async def getHash(self, manufacturerID, partNumber):
        hashUrl = f"https://webapi.autodoc.ru/api/spareparts/hash/{manufacturerID}/{partNumber}"
        async with aiohttp.request("POST", hashUrl) as response:
            responseJson = await response.json()
        return responseJson


    #! За большое число запросов банят аккаунт нахуй
    async def getToken(self):
        responseJson = await self.makeTokenRequest()

        #! Если забанят аккаунт, берём другой рандомный
        while responseJson.get("error", False):
            responseJson = await self.makeTokenRequest()
        
        accessToken = responseJson["access_token"]
        refreshToken = responseJson["refresh_token"]
        expiresIn = responseJson["expires_in"]
        tokenType = responseJson["token_type"]
    
        authData = {
            "access_token": accessToken,
            "refresh_token": refreshToken,
            "expires_in": expiresIn,
            "token_type": tokenType,
        }
        return authData 


    async def makeTokenRequest(self):
        url = "https://auth.autodoc.ru/token"
        self.account = random.choice(self.accounts)
        headers = {
            "authorization": "Bearer",
            "user-agent": self.userAgent
        }
        body = {
            "username": self.account["login"],
            "password": self.account["password"],
            "grant_type": "password"
        }
        async with aiohttp.request("POST", url, headers=headers, data=body) as response:
            responseJson = await response.json()
        return responseJson
    

    def writeToExcel(self, data):
        headers = ["Тип", "Наименование номенклатуры", "Каталожный номер", "Срок доставки", "Минимальныйы срок доставки", "Производитель", "Цена", "Поставщик"]
        writer = pd.ExcelWriter(self.ouputFilename, engine='openpyxl')
        df = pd.DataFrame(data)
        df.to_excel(writer, encoding="utf-8", index=False, header=headers)
        #! car = [{...}, {...}, ...]
        # for item in data:
        #     if not item: continue
            # sheetName = f"{car['name']} {car['carModel']}"
        writer.save()
        writer.close()

    
    def readAccountsFile(self):
        rawData = pd.read_excel("accounts.xlsx", index_col=False)
        accounts = rawData.to_numpy()
        
        accountsData = []
        for account in accounts:
            accountsData.append({
                "login": account[0],
                "password": account[1]
            })
        return accountsData


    def run(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.startParsing())
        

def log(filename, text):
    file = open(filename, "w", encoding="utf-8")
    file.write(json.dumps(text, ensure_ascii=False, indent=4))
    file.close()


if __name__ == "__main__":
    start = time.time()
    rawData = pd.read_excel("catalog_input.xlsx", header=None)
    data = [{"detailName": name, "detailNumber": number} for name, number in rawData.values.tolist()]

    autodocParser = AutodocParser(data)
    autodocParser.run()
