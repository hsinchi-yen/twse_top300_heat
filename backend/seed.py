"""
seed.py — 初始化 sector_map 種子資料

執行方式：python seed.py
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/twse_heat.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)

# 題材對照表種子資料
SEED_SECTORS = [
    # AI
    ("2330", "台積電",  "AI"),
    ("2379", "瑞昱",    "AI"),
    ("2454", "聯發科",  "AI"),
    ("3034", "聯詠",    "AI"),
    ("6770", "力積電",  "AI"),
    ("2303", "聯電",    "AI"),
    # 散熱
    ("6257", "矽格",    "散熱"),
    ("3016", "嘉澤",    "散熱"),
    ("2059", "川湖",    "散熱"),
    ("3017", "奇鋐",    "散熱"),
    ("2049", "上銀",    "散熱"),
    # 機器人
    ("2049", "上銀",    "機器人"),
    ("1590", "亞德客",  "機器人"),
    ("2368", "金像電",  "機器人"),
    # 重電
    ("1504", "東元",    "重電"),
    ("1503", "士電",    "重電"),
    ("1516", "川飛",    "重電"),
    ("1513", "中興電",  "重電"),
    ("6244", "茂迪",    "重電"),
    # 航運
    ("2603", "長榮",    "航運"),
    ("2615", "萬海",    "航運"),
    ("2609", "陽明",    "航運"),
    ("2637", "慧洋",    "航運"),
    # PCB
    ("2382", "廣達",    "PCB"),
    ("3037", "欣興",    "PCB"),
    ("2383", "台光電",  "PCB"),
    ("6598", "長科",    "PCB"),
    ("3044", "健鼎",    "PCB"),
    # 半導體
    ("2308", "台達電",  "半導體"),
    ("2344", "華邦電",  "半導體"),
    ("2337", "旺宏",    "半導體"),
    ("5347", "世界",    "半導體"),
    ("2408", "南亞科",  "半導體"),
    ("3711", "日月光",  "半導體"),
    ("6488", "環球晶",  "半導體"),
]


def seed():
    with Session() as session:
        for stock_id, _name, sector in SEED_SECTORS:
            session.execute(
                text("""
                    INSERT INTO sector_map (stock_id, sector)
                    VALUES (:stock_id, :sector)
                    ON CONFLICT(stock_id) DO UPDATE SET sector=excluded.sector
                """),
                {"stock_id": stock_id, "sector": sector},
            )
        session.commit()
    print(f"Seeded {len(SEED_SECTORS)} sector mappings.")


if __name__ == "__main__":
    seed()
