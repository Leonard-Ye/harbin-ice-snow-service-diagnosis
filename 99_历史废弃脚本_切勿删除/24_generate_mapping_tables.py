# -*- coding: utf-8 -*-
import pandas as pd
import os

out_dir = r'D:\多元大数据分析\03_方法加固与审计模块\V22_02_SMI_Model'
os.makedirs(out_dir, exist_ok=True)

# 1. xhs_to_amap_poi_mapping.csv
xhs_mapping = [
    {'xhs_location_keyword': '冰雪大世界', 'amap_standard_anchor': '哈尔滨冰雪大世界', 'match_type': '精准语义匹配', 'mapped_attributes': '热度, 负面率, 防寒痛点, 交通痛点'},
    {'xhs_location_keyword': '大世界', 'amap_standard_anchor': '哈尔滨冰雪大世界', 'match_type': '模糊别名匹配', 'mapped_attributes': '热度, 负面率, 防寒痛点, 交通痛点'},
    {'xhs_location_keyword': '索菲亚', 'amap_standard_anchor': '圣索菲亚教堂', 'match_type': '模糊别名匹配', 'mapped_attributes': '热度, 负面率, 拍照体验'},
    {'xhs_location_keyword': '索菲亚教堂', 'amap_standard_anchor': '圣索菲亚教堂', 'match_type': '精准语义匹配', 'mapped_attributes': '热度, 负面率, 拍照体验'},
    {'xhs_location_keyword': '中央大街', 'amap_standard_anchor': '中央大街', 'match_type': '精准语义匹配', 'mapped_attributes': '热度, 拥挤痛点, 餐饮痛点'},
    {'xhs_location_keyword': '太阳岛', 'amap_standard_anchor': '太阳岛风景区', 'match_type': '模糊别名匹配', 'mapped_attributes': '热度, 负面率'},
    {'xhs_location_keyword': '哈站', 'amap_standard_anchor': '哈尔滨站', 'match_type': '缩写匹配', 'mapped_attributes': '交通痛点'},
    {'xhs_location_keyword': '哈西', 'amap_standard_anchor': '哈尔滨西站', 'match_type': '缩写匹配', 'mapped_attributes': '交通痛点'}
]
pd.DataFrame(xhs_mapping).to_csv(os.path.join(out_dir, 'xhs_to_amap_poi_mapping.csv'), index=False, encoding='utf-8-sig')

# 2. dianping_comment_to_amap_mapping.csv
dp_mapping = [
    {'dianping_attribute': '商圈/景区', 'dianping_value': '中央大街', 'amap_target_type': '商圈/锚点', 'amap_standard_anchor': '中央大街', 'mapped_evidence': '餐饮排队风险, 价格压力'},
    {'dianping_attribute': '商圈/景区', 'dianping_value': '索菲亚广场', 'amap_target_type': '商圈/锚点', 'amap_standard_anchor': '圣索菲亚教堂', 'mapped_evidence': '餐饮排队风险, 服务质量下降'},
    {'dianping_attribute': '商圈/景区', 'dianping_value': '冰雪大世界', 'amap_target_type': '景区/锚点', 'amap_standard_anchor': '哈尔滨冰雪大世界', 'mapped_evidence': '园内餐饮价格, 就餐环境痛点'},
    {'dianping_attribute': '商家名称', 'dianping_value': '老厨家(中央大街店)', 'amap_target_type': '具体高德餐饮POI', 'amap_standard_anchor': '中央大街周边', 'mapped_evidence': '翻台率, 等位时间长'},
]
pd.DataFrame(dp_mapping).to_csv(os.path.join(out_dir, 'dianping_comment_to_amap_mapping.csv'), index=False, encoding='utf-8-sig')

# 3. supply_poi_source_decision_table.csv
supply_decision = [
    {'supply_dimension': '住宿服务供给 (Accommodation)', 'primary_data_source': '携程住宿 POI (5871条)', 'secondary_validation_source': '高德住宿 POI', 'avoid_double_count_strategy': 'SSI 计算中仅使用携程数据，剔除高德住宿，防止重叠计算。'},
    {'supply_dimension': '餐饮服务供给 (Dining)', 'primary_data_source': '高德餐饮 POI (050000)', 'secondary_validation_source': '大众点评', 'avoid_double_count_strategy': '高德提供物理点位数量；大众点评不作为点位计数，仅作为排队/价格/体验压力的旁证属性。'},
    {'supply_dimension': '交通设施供给 (Transport)', 'primary_data_source': '高德交通设施 POI (150000)', 'secondary_validation_source': '无', 'avoid_double_count_strategy': '独家采用高德底图。'},
    {'supply_dimension': '公共设施供给 (Public)', 'primary_data_source': '高德公共设施 POI (200000)', 'secondary_validation_source': '无', 'avoid_double_count_strategy': '独家采用高德底图。'},
    {'supply_dimension': '医疗保健供给 (Medical)', 'primary_data_source': '高德医疗保健 POI (090000) [待扩充]', 'secondary_validation_source': '无', 'avoid_double_count_strategy': '用于防寒/急救痛点的对应供给。'},
    {'supply_dimension': '购物与保暖供给 (Shopping)', 'primary_data_source': '高德购物服务 POI (060000) [待扩充]', 'secondary_validation_source': '无', 'avoid_double_count_strategy': '用于购买防寒物资的供给对应。'},
    {'supply_dimension': '体育休闲与洗浴 (Leisure)', 'primary_data_source': '高德体育休闲 POI (080000) [待扩充]', 'secondary_validation_source': '无', 'avoid_double_count_strategy': '东北特色回血设施。'}
]
pd.DataFrame(supply_decision).to_csv(os.path.join(out_dir, 'supply_poi_source_decision_table.csv'), index=False, encoding='utf-8-sig')

print("Mapping tables generated successfully.")
