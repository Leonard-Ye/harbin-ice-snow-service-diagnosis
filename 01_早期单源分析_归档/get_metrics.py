import pandas as pd

with open("alpha_patch_metrics.txt", "w", encoding="utf-8") as f:
    df1 = pd.read_csv('analysis_outputs_phase4/tables/xhs_checkin_note_source_mapping.csv')
    rate = (df1['match_status'] == 'Matched').mean()
    f.write(f"Mapping rate: {rate:.2%}\n")
    
    df2 = pd.read_csv('analysis_outputs_phase4/tables/xhs_checkin_note_subset.csv')
    f.write(f"Subset count: {len(df2)}\n")
    
    df_locs = pd.read_csv('analysis_outputs_phase4/tables/xhs_checkin_locations_long.csv')
    loc_coverage = df_locs['note_id'].nunique() / len(df2)
    f.write(f"Location Coverage: {loc_coverage:.2%}\n")
    
    df3 = pd.read_csv('analysis_outputs_phase4/tables/xhs_checkin_poi_sentiment_join.csv')
    f.write("\nTop 20 POIs:\n")
    f.write(df3.head(20)[['normalized_location', 'total_heat_score', 'negative_ratio']].to_string())
    
    df4 = pd.read_csv('analysis_outputs_phase4/tables/xhs_checkin_heat_risk_quadrant.csv')
    f.write("\n\nHigh Heat High Risk:\n")
    f.write(df4[df4['quadrant_type'] == '重点治理点'][['normalized_location', 'total_heat_score', 'negative_ratio']].to_string())
    f.write("\n\nHigh Heat Low Risk:\n")
    f.write(df4[df4['quadrant_type'] == '城市形象样板点'][['normalized_location', 'total_heat_score', 'negative_ratio']].to_string())
