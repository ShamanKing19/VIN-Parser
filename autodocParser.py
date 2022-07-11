import asyncio
import itertools
import json
from pprint import pprint
import random
import time
import aiohttp
import pandas as pd
from tqdm import tqdm
# pip install xlsxwriter
# pip install openpyxl
# pip install pandas
# pip install aiohttp
# pip install asyncio


class AutodocParser:
    def __init__(self, data):
        self.timeout = 5
        self.sessionTimeout = aiohttp.ClientTimeout(
            total=None, sock_connect=self.timeout, sock_read=self.timeout)
        self.connector = aiohttp.TCPConnector(ssl=False, limit=10000)
        self.session = aiohttp.ClientSession(
            connector=self.connector, timeout=self.sessionTimeout)
        self.data = data
        self.tokenPostData = {
            "username": "KNG-16078",
            "password": "6sqqSZ77PHZPmEL",
            "grant_type": "password"
        }
        self.inputFilename = "input.xlsx"
        self.ouputFilename = "output.xlsx"


    def run(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.startParsing())


    async def startParsing(self):
        requestsList = []
        # * Запросы по VIN
        for vin in self.data:
            request = self.makePrimaryRequest(vin)
            requestsList.append(request)
        responses = await asyncio.gather(*requestsList)
        requestsList.clear()

        # *  Основная информация по машинам
        primaryData = []
        for response in responses:
            primaryData.append(self.collectPrimaryData(response))
        carsPrimaryInfo = await asyncio.gather(*primaryData)


        # * Парсинг по VIN по машине
        requestsList = []
        for carData in carsPrimaryInfo:
            requestsList.append(self.parseVINs(carData))
        carsInfo = await asyncio.gather(*requestsList)
        self.session.close()
        self.writeToExcel(carsInfo)


    async def parseVINs(self, carInfo):
        if not carInfo: return
        detailsData = []
        uniqueParts = []

        carID = carInfo.get("CarID", "0")
        carModel = carInfo.get("Model", "")

        categoriesUrl = f"https://catalogoriginal.autodoc.ru/api/catalogs/original/brands/{carInfo['Catalog']}/cars/{carID}/categories?ssd={carInfo['Ssd']}".strip()
        response = await self.session.get(categoriesUrl)
        carSparePartsCategories = await response.json()

        categories = carSparePartsCategories.get("items", []) if "items" in carSparePartsCategories.keys() else carSparePartsCategories
        
        # Получение всех подкатегорий
        subcategories = [self.getChildrenList(category.get("children", [])) for category in categories]
        subcats = list(itertools.chain(*subcategories))
        allCategories = categories + subcats

        for partCategory in tqdm(allCategories):
            sparePartInfoUrl = f"https://catalogoriginal.autodoc.ru/api/catalogs/original/brands/{carInfo['Catalog']}/cars/0/categories/{partCategory['categoryId']}/units?ssd={partCategory['ssd']}"
            sparePartInfoResponse = await self.session.get(sparePartInfoUrl)
            sparePartInfoResponseJson = await sparePartInfoResponse.json()

            for sparePartsInfo in sparePartInfoResponseJson.get("items", []):
                sparePartDetailInfoUrl = f"https://catalogoriginal.autodoc.ru/api/catalogs/original/brands/{carInfo['Catalog']}/cars/0/units/{sparePartsInfo['unitId']}/spareparts?ssd={sparePartsInfo['ssd']}"
                data = {
                    "Ssd": sparePartsInfo['ssd']
                }
                sparePartDetailInfoResponse = await self.session.post(sparePartDetailInfoUrl, data=data)
                sparePartDetailInfoResponseJson = await sparePartDetailInfoResponse.json()
                spareParts = sparePartDetailInfoResponseJson.get("items", [])
                

                for sparePart in spareParts:
                    # Фильтр дубликатов #! Возможно из-за этого будут проблемы, могут попросить оставить дубли деталей
                    if sparePart["partNumber"] not in uniqueParts:
                        uniqueParts.append(sparePart["partNumber"])
                        
                        detailsData.append({
                            "category": partCategory["name"],
                            "partName": sparePart["name"],
                            "partNumber": sparePart["partNumber"]
                        })
                    else:
                        continue

        outputData = {
            "name": carInfo['Catalog'],
            "carModel": carModel,
            "items": detailsData
        }
        return outputData


    def getChildrenList(self, node):
        items = []
        for item in node:
            if isinstance(item, str): return items
            children = item.get("children", {})
            if children:
                items = self.getChildrenList(item)
            else:
                items.append(item)
        return items



    # Обычные запросы по VIN
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


    async def makePrimaryRequest(self, vin):
        clientId = random.randint(0, 500)
        # clientId = 333

        keyUrl = f"https://catalogoriginal.autodoc.ru/api/catalogs/original/cars/{vin}/modifications?clientId={clientId}"
        response = await self.session.get(keyUrl)
        return response

    
    def writeToExcel(self, carsData):
        writer = pd.ExcelWriter(self.ouputFilename, engine='openpyxl')
        #! car = [{...}, {...}, ...]
        for car in carsData:
            if not car: continue
            items = car["items"]
            sheetName = f"{car['name']} {car['carModel']}"
            df = pd.DataFrame(items)
            df.to_excel(writer, sheet_name=sheetName, encoding="utf-8", index=False)
            writer.save()
        writer.close()


if __name__ == "__main__":
    start = time.time()
    vins = pd.read_excel("input.xlsx", header=None)
    data = [vin[0] for vin in vins.values.tolist()]

    autodocParser = AutodocParser(data)
    autodocParser.run()
    
    print(time.time() - start)
