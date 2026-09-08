import pymysql

conn = pymysql.connect(
    host="web.dcism.org",
    port=3306,
    user="s07402931_Ware67",
    password="LLware67",
    database="s07402931_Ware67",
)
print("Connected!")
conn.close()