import asyncio
from pprint import pprint
import aiohttp
import requests


class AutodocParser:
    def __init__(self, data):
        # Здесь в ответе есть Ssd
        self.keyUrl = "https://catalogoriginal.autodoc.ru/api/catalogs/original/cars/Z8NAJL01051621776/modifications?clientId=375"
        self.SsdKey = "KwFZbXxtWDkmFV5eKlhqWwEVNTIsXFtdW0xKSQ8qFk4CHk9VEGppJUhBTgIZT1UQZhglKycgW1tdWgMKElpdWlpJRk8KUx4aMDcQAAAAAKU0G6w"
        # В каждом запросе используется этот SsdKey
        # self.carInfoUrl = "Request URL: https://catalogoriginal.autodoc.ru/api/catalogs/original/catalogCodes/NISSAN201809?ssd=$*KwFZbXxtWDkmFV5eKlhqWwEVNTIsXFtdW0xKSQ8qFk4CHk9VEGppJUhBTgIZT1UQZhglKycgW1tdWgMKElpdWlpJRk8KUx4aMDcQAAAAAKU0G6w=$"
        self.categoriesUrl = "https://catalogoriginal.autodoc.ru/api/catalogs/original/brands/NISSAN201809/cars/0/categories?ssd=$*KwFZbXxtWDkmFV5eKlhqWwEVNTIsXFtdW0xKSQ8qFk4CHk9VEGppJUhBTgIZT1UQZhglKycgW1tdWgMKElpdWlpJRk8KUx4aMDcQAAAAAKU0G6w=$"
        self.quickGroupsUrl = "Request URL: https://catalogoriginal.autodoc.ru/api/catalogs/original/brands/NISSAN201809/cars/0/quickgroups?ssd=$*KwFZbXxtWDkmFV5eKlhqWwEVNTIsXFtdW0xKSQ8qFk4CHk9VEGppJUhBTgIZT1UQZhglKycgW1tdWgMKElpdWlpJRk8KUx4aMDcQAAAAAKU0G6w=$"
        self.tokenUrl = "https://auth.autodoc.ru/token"
        self.timeout = 5
        self.sessionTimeout = aiohttp.ClientTimeout(total=None, sock_connect=self.timeout, sock_read=self.timeout)
        self.connector = aiohttp.TCPConnector(ssl=False, limit=10000)
        self.session = aiohttp.ClientSession(connector=self.connector, timeout=self.sessionTimeout)
        self.data = data
        self.tokenPostData = {
            "username": "KNG-16078",
            "password": "6sqqSZ77PHZPmEL",
            "grant_type": "password"
        }


    def run(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.startParsing())
        

    async def startParsing(self): 
        requests = []       
        ### * Запросы по VIN
        for item in self.data:
            request = self.makePrimaryRequest(item["VIN"], item["CLIENT_ID"])
            requests.append(request)       
        responses = await asyncio.gather(*requests)
        requests.clear()

        ### *  Основная информация по машине
        primaryData = []
        for response in responses:
            primaryData.append(self.collectPrimaryData(response))
        carsPrimaryInfo = await asyncio.gather(*primaryData)

        ### * Категории запчастей (1-й уровень)
        requests = []
        for car in carsPrimaryInfo:
            categoriesUrl = f"https://catalogoriginal.autodoc.ru/api/catalogs/original/brands/{car['Catalog']}/cars/0/categories?ssd={car['Ssd']}"
            response = await self.session.get(categoriesUrl)
            carSparePartsCategories = await response.json()
            ### * Информация о категории запчастей #* (2-й уровень)
            for sparePart in carSparePartsCategories["items"]:
                sparePartInfoUrl = f"https://catalogoriginal.autodoc.ru/api/catalogs/original/brands/{car['Catalog']}/cars/0/categories/{sparePart['categoryId']}/units?ssd={sparePart['ssd']}"
                sparePartInfoResponse = await self.session.get(sparePartInfoUrl)
                sparePartInfoResponseJson = await sparePartInfoResponse.json()
                for sparePartsInfo in sparePartInfoResponseJson.get("items", []):
                    sparePartDetailInfoUrl = f"https://catalogoriginal.autodoc.ru/api/catalogs/original/brands/{car['Catalog']}/cars/0/units/{sparePartsInfo['unitId']}/spareparts?ssd={sparePartsInfo['ssd']}"
                    data = {
                        "content-type": "application/json"
                    }
                    # TODO: РАЗОБРАТЬСЯ !!! Тут надо посылать json
                    sparePartDetailInfoResponse = await self.session.post(sparePartDetailInfoUrl, data=data)
                    sparePartDetailInfoResponseJson = await sparePartDetailInfoResponse.json()
                    pprint(sparePartDetailInfoResponseJson)
                
                print("\n\n\n")
        

    async def GetToken(self):
        headers = {
            "content-type:" : "application/json;charset=UTF-8"
        }
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), headers=headers)
        response = await session.post(self.tokenUrl, self.tokenPostData)
        print(await response.json())


        ### * Информация об узлах запчастей #* (2-й уровень)
        quickGroupsUrl = f"https://catalogoriginal.autodoc.ru/api/catalogs/original/brands/NISSAN201809/cars/0/quickgroups?ssd=$*KwFZbXxtWDkmFV5eKlhqWwEVNTIsXFtdW0xKSQ8qFk4CHk9VEGppJUhBTgIZT1UQZhglKycgW1tdWgMKElpdWlpJRk8KUx4aMDcQAAAAAKU0G6w=$"

        await self.session.close()


    async def collectPrimaryData(self, response):
        carPrimaryInfo = {}
        responseData = await response.json()
        
        try:
            primaryData = responseData["commonAttributes"]
        except Exception as error:
            print(error)
            return

        for attribute in primaryData:
            carPrimaryInfo[attribute["key"]] = attribute["value"]
        return carPrimaryInfo
    




    async def makePrimaryRequest(self, vin, clientId):
        # VIN: Z8NAJL01051621776
        # clientId: 375
        keyUrl = f"https://catalogoriginal.autodoc.ru/api/catalogs/original/cars/{vin}/modifications?clientId={clientId}"
        response = await self.session.get(keyUrl)
        return response
    





if __name__ == "__main__":
    data = [
            {
                "VIN": "Z8NAJL01051621776",
                "CLIENT_ID": 375
            },
            {
                "VIN": "WDDMH4EB1FJ311912",
                "CLIENT_ID": 378
            },

        ]
    autodocParser = AutodocParser(data)
    autodocParser.run()
