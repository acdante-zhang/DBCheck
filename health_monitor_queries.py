# -*- coding: utf-8 -*-
"""
健康监控 SQL 查询模板
支持 Oracle / MySQL / PostgreSQL / TiDB / DM8
"""

# ============================================================
# Oracle 健康监控 SQL
# ============================================================
ORACLE_HEALTH_SQL = {
    'rac_status': """
        SELECT inst_id, instance_name, host_name, status,
               database_status, instance_role,
               TO_CHAR(startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time,
               ROUND((SYSDATE - startup_time) * 24, 1) AS uptime_hours,
               version
        FROM gv$instance
        ORDER BY inst_id
    """,

    'db_size': """
        SELECT
            (SELECT ROUND(SUM(bytes)/1073741824, 2) FROM dba_data_files) AS datafile_gb,
            (SELECT ROUND(SUM(bytes)/1073741824, 2) FROM dba_segments) AS segment_gb
        FROM dual
    """,

    'adg_status': """
        SELECT d.database_role, d.protection_mode, d.protection_level,
               d.open_mode, d.switchover_status,
               (SELECT COUNT(*) FROM v$archive_dest_status
                WHERE type='PHYSICAL' AND status='VALID') AS standby_count,
               (SELECT NVL(MAX(ROUND(
                   (SYSDATE - TO_DATE(SUBSTR(TO_CHAR(time_computed),1,19),
                    'YYYY-MM-DD HH24:MI:SS')) * 24 * 60, 1)), 0)
                FROM v$dataguard_stats
                WHERE name = 'apply lag'
                  AND time_computed IS NOT NULL
                  AND ROWNUM = 1) AS max_apply_lag_min,
               (SELECT LISTAGG(dest_id || ':' || status, ', ')
                WITHIN GROUP (ORDER BY dest_id)
                FROM v$archive_dest_status
                WHERE type='PHYSICAL' AND status != 'INACTIVE') AS dest_details
        FROM v$database d
    """,

    'backup_status': """
        SELECT * FROM (
            SELECT TO_CHAR(start_time,'YYYY-MM-DD HH24:MI') AS backup_time,
                   status, input_type,
                   ROUND(input_bytes/1073741824,2) AS size_gb,
                   ROUND(elapsed_seconds/60,1) AS duration_min,
                   output_device_type
            FROM v$rman_backup_job_details
            WHERE start_time > SYSDATE - 30
            ORDER BY start_time DESC
        ) WHERE ROWNUM <= 7
    """,

    'asm_diskgroup': """
        SELECT name, type, state,
               ROUND(total_mb/1024,2) AS total_gb,
               ROUND((total_mb-free_mb)/1024,2) AS used_gb,
               ROUND(free_mb/1024,2) AS free_gb,
               ROUND((1-free_mb/NULLIF(total_mb,0))*100,1) AS usage_pct
        FROM v$asm_diskgroup
        ORDER BY name
    """,

    'tablespace_usage': """
        SELECT t.tablespace_name,
               ROUND(GREATEST(NVL(SUM(df.bytes),0), NVL(SUM(df.maxbytes),0))/1073741824,2) AS total_gb,
               ROUND((NVL(SUM(df.bytes),0) - NVL(SUM(fs.bytes),0))/1073741824,2) AS used_gb,
               ROUND((NVL(SUM(df.bytes),0) - NVL(SUM(fs.bytes),0)) /
                     NULLIF(GREATEST(NVL(SUM(df.bytes),0), NVL(SUM(df.maxbytes),0)), 0) * 100, 1) AS usage_pct,
               COUNT(df.file_name) AS datafile_count,
               CASE WHEN (NVL(SUM(df.bytes),0) - NVL(SUM(fs.bytes),0)) /
                        NULLIF(GREATEST(NVL(SUM(df.bytes),0), NVL(SUM(df.maxbytes),0)), 0) * 100 > 90
                    THEN 'CRITICAL'
                    WHEN (NVL(SUM(df.bytes),0) - NVL(SUM(fs.bytes),0)) /
                        NULLIF(GREATEST(NVL(SUM(df.bytes),0), NVL(SUM(df.maxbytes),0)), 0) * 100 > 80
                    THEN 'WARNING'
                    ELSE 'OK' END AS status
        FROM dba_tablespaces t
        LEFT JOIN dba_data_files df
               ON df.tablespace_name = t.tablespace_name
        LEFT JOIN (SELECT tablespace_name, SUM(bytes) AS bytes
                   FROM dba_free_space GROUP BY tablespace_name) fs
               ON fs.tablespace_name = t.tablespace_name
        WHERE t.contents = 'PERMANENT'
        GROUP BY t.tablespace_name
        ORDER BY usage_pct DESC
    """,

    'session_stats': """
        SELECT
            (SELECT COUNT(*) FROM v$session) AS total_sessions,
            (SELECT TO_NUMBER(value) FROM v$parameter WHERE name='sessions') AS session_limit,
            (SELECT COUNT(*) FROM v$session WHERE status='ACTIVE') AS active_sessions,
            (SELECT COUNT(*) FROM v$session WHERE status='INACTIVE') AS inactive_sessions,
            (SELECT COUNT(*) FROM v$session WHERE type='BACKGROUND') AS background_sessions,
            ROUND((SELECT COUNT(*) FROM v$session)/
                  NULLIF((SELECT TO_NUMBER(value) FROM v$parameter WHERE name='sessions'),0)*100,1) AS usage_pct
        FROM dual
    """,

    'schema_users': """
        SELECT username, account_status,
               TO_CHAR(created,'YYYY-MM-DD') AS created_date,
               default_tablespace, temporary_tablespace
        FROM dba_users
        WHERE oracle_maintained='N'
        ORDER BY username
    """,

    'instance_info': """
        SELECT instance_name, host_name, version, status,
               TO_CHAR(startup_time,'YYYY-MM-DD HH24:MI:SS') AS startup_time,
               database_status, instance_role
        FROM v$instance
    """,
}

# ============================================================
# MySQL / TiDB 健康监控 SQL
# ============================================================
MYSQL_HEALTH_SQL = {
    'db_size': """
        SELECT ROUND(SUM(data_length+index_length)/1073741824,2) AS total_gb,
               ROUND(SUM(data_length)/1073741824,2) AS data_gb,
               ROUND(SUM(index_length)/1073741824,2) AS index_gb
        FROM information_schema.tables
        WHERE table_schema NOT IN ('mysql','sys','information_schema','performance_schema')
    """,

    'tablespace_usage': """
        SELECT table_schema AS tablespace_name,
               ROUND(SUM(data_length+index_length)/1073741824,2) AS total_gb,
               ROUND(SUM(data_length)/1073741824,2) AS used_gb,
               ROUND(SUM(data_length)/NULLIF(SUM(data_length+index_length),0)*100,1) AS usage_pct,
               CASE WHEN SUM(data_length)/NULLIF(SUM(data_length+index_length),0)*100 > 90
                    THEN 'CRITICAL'
                    WHEN SUM(data_length)/NULLIF(SUM(data_length+index_length),0)*100 > 80
                    THEN 'WARNING'
                    ELSE 'OK' END AS status
        FROM information_schema.tables
        WHERE table_schema NOT IN ('mysql','sys','information_schema','performance_schema')
        GROUP BY table_schema
        ORDER BY total_gb DESC
        LIMIT 20
    """,

    'session_stats': """
        SELECT COUNT(*) AS total_sessions,
               @@max_connections AS session_limit,
               SUM(CASE WHEN command!='Sleep' THEN 1 ELSE 0 END) AS active_sessions,
               SUM(CASE WHEN command='Sleep' THEN 1 ELSE 0 END) AS inactive_sessions,
               ROUND(COUNT(*)/NULLIF(@@max_connections,0)*100,1) AS usage_pct
        FROM information_schema.processlist
    """,

    'instance_info': """
        SELECT @@hostname AS host_name, VERSION() AS version,
               @@port AS port, DATABASE() AS current_db
    """,

    'backup_status': """
        SELECT 'N/A (MySQL backup check requires external tool)' AS note
        LIMIT 1
    """,
}

# ============================================================
# PostgreSQL / IvorySQL 健康监控 SQL
# ============================================================
PG_HEALTH_SQL = {
    'db_size': """
        SELECT pg_database.datname,
               pg_size_pretty(pg_database_size(pg_database.datname)) AS size_pretty,
               ROUND(pg_database_size(pg_database.datname)/1073741824.0, 2) AS size_gb
        FROM pg_database
        WHERE datistemplate = false
        ORDER BY pg_database_size(pg_database.datname) DESC
    """,

    'tablespace_usage': """
        SELECT spcname AS tablespace_name,
               pg_size_pretty(pg_tablespace_size(spcname)) AS size_pretty,
               ROUND(pg_tablespace_size(spcname)/1073741824.0, 2) AS total_gb
        FROM pg_tablespace
        ORDER BY pg_tablespace_size(spcname) DESC
    """,

    'session_stats': """
        SELECT COUNT(*) AS total_sessions,
               current_setting('max_connections')::int AS session_limit,
               COUNT(*) FILTER (WHERE state='active') AS active_sessions,
               COUNT(*) FILTER (WHERE state='idle') AS inactive_sessions,
               ROUND(COUNT(*)*100.0/NULLIF(current_setting('max_connections')::int,0),1) AS usage_pct
        FROM pg_stat_activity
        WHERE backend_type = 'client backend'
    """,

    'instance_info': """
        SELECT inet_server_addr()::text AS host_name,
               version() AS version,
               inet_server_port() AS port,
               current_database() AS current_db
    """,

    'backup_status': """
        SELECT 'N/A (PG backup check requires external tool)' AS note
        LIMIT 1
    """,
}

# ============================================================
# DM8 (达梦) 健康监控 SQL
# ============================================================
DM_HEALTH_SQL = {
    'db_size': """
        SELECT
            ROUND(SUM(bytes)/1073741824, 2) AS datafile_gb
        FROM dba_data_files
    """,

    'tablespace_usage': """
        SELECT t.name AS tablespace_name,
               ROUND(t.total_size*sf.pagesize/1073741824, 2) AS total_gb,
               ROUND((t.total_size-t.free_size)*sf.pagesize/1073741824, 2) AS used_gb,
               ROUND((1-t.free_size/NULLIF(t.total_size,0))*100, 1) AS usage_pct
        FROM v$tablespace t
        CROSS JOIN (SELECT pagesize FROM v$database) sf
        ORDER BY usage_pct DESC
    """,

    'session_stats': """
        SELECT COUNT(*) AS total_sessions,
               (SELECT MAX_SESSIONS FROM v$database) AS session_limit,
               COUNT(CASE WHEN state='ACTIVE' THEN 1 END) AS active_sessions,
               COUNT(CASE WHEN state='IDLE' THEN 1 END) AS inactive_sessions
        FROM v$sessions
    """,

    'instance_info': """
        SELECT name AS instance_name, host_name, version, status$,
               TO_CHAR(start_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time
        FROM v$instance
    """,
}

# ============================================================
# 数据库类型 → SQL 模板映射
# ============================================================
DB_HEALTH_SQL_MAP = {
    'oracle': ORACLE_HEALTH_SQL,
    'oracle_rac': ORACLE_HEALTH_SQL,
    'mysql': MYSQL_HEALTH_SQL,
    'tidb': MYSQL_HEALTH_SQL,
    'postgresql': PG_HEALTH_SQL,
    'ivorysql': PG_HEALTH_SQL,
    'kingbase': PG_HEALTH_SQL,
    'dm': DM_HEALTH_SQL,
    'dm8': DM_HEALTH_SQL,
    'gbase': ORACLE_HEALTH_SQL,  # GBase 8s 语法接近 Oracle
}

# 每种数据库类型支持的卡片列表
DB_SUPPORTED_CARDS = {
    'oracle': ['rac_status','db_size','adg_status','backup_status',
               'asm_diskgroup','tablespace_usage','session_stats','schema_users','instance_info'],
    'oracle_rac': ['rac_status','db_size','adg_status','backup_status',
                   'asm_diskgroup','tablespace_usage','session_stats','schema_users','instance_info'],
    'mysql': ['db_size','tablespace_usage','session_stats','instance_info'],
    'tidb': ['db_size','tablespace_usage','session_stats','instance_info'],
    'postgresql': ['db_size','tablespace_usage','session_stats','instance_info'],
    'ivorysql': ['db_size','tablespace_usage','session_stats','instance_info'],
    'kingbase': ['db_size','tablespace_usage','session_stats','instance_info'],
    'dm': ['db_size','tablespace_usage','session_stats','instance_info'],
    'dm8': ['db_size','tablespace_usage','session_stats','instance_info'],
}

# 卡片显示配置
CARD_DISPLAY_CONFIG = {
    'rac_status':       {'title': 'RAC 集群状态',  'icon': '🖥️',  'order': 1,  'size': 'large'},
    'db_size':          {'title': '数据库总大小',   'icon': '💾',  'order': 2,  'size': 'medium'},
    'adg_status':       {'title': 'ADG 同步状态',   'icon': '🔄',  'order': 3,  'size': 'medium'},
    'backup_status':    {'title': '备份状态',       'icon': '💿',  'order': 4,  'size': 'medium'},
    'asm_diskgroup':    {'title': 'ASM 磁盘组',     'icon': '💽',  'order': 5,  'size': 'medium'},
    'tablespace_usage': {'title': '表空间使用率',   'icon': '📊',  'order': 6,  'size': 'large'},
    'session_stats':    {'title': '会话统计',       'icon': '👥',  'order': 7,  'size': 'small'},
    'schema_users':     {'title': 'Schema 用户',    'icon': '👤',  'order': 8,  'size': 'large'},
    'instance_info':    {'title': '实例信息',       'icon': 'ℹ️',  'order': 0,  'size': 'small'},
}
