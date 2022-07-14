import asyncio
from pprint import pprint
import random
import time
import pandas as pd

import aiohttp
from fake_useragent import UserAgent

class AutodocParser:
    def __init__(self, data):
        self.ouputFilename = "catalog_output.xlsx"
        self.timeout = 5
        self.sessionTimeout = aiohttp.ClientTimeout(total=None, sock_connect=self.timeout, sock_read=self.timeout)
        self.connector = aiohttp.TCPConnector(ssl=False, limit=10000)
        self.data = data
        self.userAgent = UserAgent().random

        self.loginUrl = "https://webapi.autodoc.ru/api/account/login"
        self.login = "KNG-16078"
        self.password = "6sqqSZ77PHZPmEL"
        self.loginAttempts = ["DC1/O1127x9ZL4GU2bhQgg==", "W7F+x+sPZUPsCAcXwYSH5Q=="]
        


    async def startParsing(self):
        challengeGuid = await self.getChallengeGuid()
        tokenData = await self.getToken()
        loginData = await self.getLoginData(tokenData, challengeGuid, random.choice(self.loginAttempts))
        pprint(loginData)
        if loginData["clientStatus"] != 0:
            await self.startParsing()
            return
        # profileData = await self.getProfileData()


        # print(f"challengeGuid: {challengeGuid}\n")
        # pprint(profileData)
        # hash = await self.getHash()
        # self.session = await self.createSession(authData, hash)

        # hash = await self.getHash()
        # newSession = await self.createSession(authData, hash)
        # for detailData in self.data:
        #     detailName = detailData["detailName"]
        #     detailNumber = detailData["detailNumber"]
        #     carID = await self.getCarID(newSession, detailNumber)
        #     print(carID)

        # await self.session.close()





    # TODO: Понять как правильно авторизовываться чтобы получать данные о стоимости и сроках доставки детали
    async def makeApiRequest(self, detailNumber):
        detailUrl = "https://webapi.autodoc.ru/api/spareparts/657/N0138321/2?framesId=undefined&attempt=undefined&isrecross=false"
        response = await self.session.get(detailUrl)
        return await response.text()
        # responseJson = await response.json()



    async def getCarID(self, session, partNumber):
        url = f"https://webapi.autodoc.ru/api/manufacturers/{partNumber}?showAll=false"
        response = await session.get(url)
        responseJson = await response.json()
        # carID = responseJson["id"]
        # return carID

    
    async def getProfileData(self):
        url = "https://webapi.autodoc.ru/api/client/profile"
        async with aiohttp.request("GET", url) as response:
            responseJson = await response.json()
        return responseJson


    async def getLoginData(self, authData, challengeGuid, attempt):
        url = "https://webapi.autodoc.ru/api/account/login"
        
        headers = {
            "authorization": authData["token_type"] + " " + authData["access_token"],
            "user-agent": self.userAgent
        }
        
        data = {
            "attempt": attempt,
            "challengeGuid": challengeGuid,
            "gRecaptchaResponse": "",
            "login": self.login,
            "password": self.password,
            "rememberMe": "true"
        }
        
        async with aiohttp.request("POST", url, headers=headers, data=data) as response:
            responseJson = await response.json()
            clientStatus = responseJson["clientStatus"]
        return responseJson


    async def createSession(self, authData, hash) -> aiohttp.ClientSession:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
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


    async def getHash(self, carID, partNumber):
        hashUrl = f"https://webapi.autodoc.ru/api/spareparts/hash/{carID}/{partNumber}"
        async with aiohttp.request("POST", hashUrl) as response:
            responseJson = await response.json()
        return responseJson


    async def getToken(self):
        url = "https://auth.autodoc.ru/token"

        headers = {
            "authorization": "Bearer",
            "user-agent": self.userAgent
        }

        body = {
            "username": self.login,
            "password": self.password,
            "grant_type": "password"
        }
        async with aiohttp.request("POST", url, headers=headers, data=body) as response:
            responseJson = await response.json()
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


    def run(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.startParsing())
        


if __name__ == "__main__":
    start = time.time()
    rawData = pd.read_excel("catalog_input.xlsx", header=None)
    data = [{"detailName": name, "detailNumber": number} for name, number in rawData.values.tolist()]

    autodocParser = AutodocParser(data)
    autodocParser.run()

    # print(time.time() - start)
