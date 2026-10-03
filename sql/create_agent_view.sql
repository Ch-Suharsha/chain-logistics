CREATE OR REPLACE VIEW cold_chain.v_agent_fleet AS
SELECT
    TS_UTC,
    V_LAT,
    V_LON,
    IOT_TEMP_VAL_C,
    CGO_COND_CD,
    RISK_CLS_TXT,
    DELAY_PROB_DEC,
    PRT_CNG_LVL,
    RT_RSK_IDX,
    SYS_INGEST_FLAG
FROM cold_chain.tbl_sc_fleet_hist_raw;
