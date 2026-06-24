# -*- coding: utf-8 -*-
"""
数据库健康监控引擎 — 后台定时采集
单例模式，复用 InstanceManager 获取解密连接信息
"""

import threading
import time
import traceback
from collections import deque
from datetime import datetime

from health_monitor_queries import (
    DB_HEALTH_SQL_MAP, DB_SUPPORTED_CARDS, CARD_DISPLAY_CONFIG
)


class HealthMonitorEngine:
    """数据库健康监控引擎 — 全局单例"""

    DEFAULT_INTERVAL = 30
    MAX_HISTORY = 48
    QUERY_TIMEOUT = 30

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data_lock = threading.Lock()
        self._running = False
        self._thread = None
        self._interval = self.DEFAULT_INTERVAL
        self._instance_ids = []
        self._health_data = {}  # {instance_id: {cards: {}, error: str, ts: float, db_type: str}}
        self._history = deque(maxlen=self.MAX_HISTORY)

    # ── 生命周期 ──────────────────────────────────────────

    def start(self, instance_ids=None):
        """启动采集，instance_ids 指定要监控的实例 ID 列表"""
        if instance_ids:
            self._instance_ids = list(instance_ids)

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()
        print(f"[HealthMonitor] 启动，监控 {len(self._instance_ids)} 个实例，间隔 {self._interval}s")

    def stop(self):
        self._running = False

    def set_instance_ids(self, instance_ids):
        self._instance_ids = list(instance_ids)

    def set_interval(self, interval):
        self._interval = max(5, min(300, interval))

    # ── 数据访问 ──────────────────────────────────────────

    def get_health_data(self, instance_id=None, allowed_ids=None):
        """获取健康数据快照"""
        with self._data_lock:
            if instance_id:
                return self._health_data.get(str(instance_id))
            data = dict(self._health_data)
        if allowed_ids is not None:
            data = {k: v for k, v in data.items() if k in allowed_ids}
        return data

    def get_history(self):
        return list(self._history)

    def get_status(self):
        return {
            'running': self._running,
            'interval': self._interval,
            'instance_count': len(self._instance_ids),
            'last_update': max(
                (v.get('ts', 0) for v in self._health_data.values()), default=0
            ),
        }

    # ── 采集循环 ──────────────────────────────────────────

    def _collect_loop(self):
        while self._running:
            start = time.time()
            for iid in list(self._instance_ids):
                try:
                    self._collect_one(iid)
                except Exception as e:
                    with self._data_lock:
                        self._health_data[str(iid)] = {
                            'instance_id': str(iid),
                            'error': str(e),
                            'ts': time.time(),
                            'cards': {},
                            'db_type': 'unknown',
                        }
            elapsed = time.time() - start
            sleep_time = max(1, self._interval - elapsed)
            time.sleep(sleep_time)

    def _collect_one(self, instance_id):
        """采集单个实例的所有卡片数据"""
        iid = str(instance_id)
        from pro.instance_manager import get_instance_manager
        im = get_instance_manager()
        try:
            inst = im.get_instance_decrypted(int(instance_id))
        except Exception:
            inst = None
        if not inst:
            raise ValueError(f"实例 {instance_id} 不存在或解密失败")

        db_type = inst.get('db_type', '').lower()
        sql_map = DB_HEALTH_SQL_MAP.get(db_type, {})
        supported = DB_SUPPORTED_CARDS.get(db_type, [])
        cards = {}
        error = None

        conn = None
        try:
            conn = self._connect(inst, db_type)
            for card_type in supported:
                sql = sql_map.get(card_type)
                if not sql:
                    continue
                try:
                    rows = self._execute(conn, sql, db_type)
                    cards[card_type] = rows
                except Exception as card_err:
                    cards[card_type] = {'_error': str(card_err)}
        except Exception as conn_err:
            error = str(conn_err)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        with self._data_lock:
            self._health_data[iid] = {
                'instance_id': iid,
                'label': inst.get('name', f"{inst.get('host')}:{inst.get('port')}"),
                'db_type': db_type,
                'host': inst.get('host', ''),
                'port': inst.get('port', ''),
                'cards': cards,
                'error': error,
                'ts': time.time(),
            }

    # ── 数据库连接 ────────────────────────────────────────

    def _connect(self, inst, db_type):
        if db_type in ('mysql', 'tidb'):
            import pymysql
            return pymysql.connect(
                host=inst['host'], port=inst['port'],
                user=inst['user'], password=inst['password'],
                database=inst.get('database', ''),
                connect_timeout=self.QUERY_TIMEOUT,
                charset='utf8mb4',
            )
        elif db_type in ('postgresql', 'ivorysql', 'kingbase'):
            import psycopg2
            return psycopg2.connect(
                host=inst['host'], port=inst['port'],
                user=inst['user'], password=inst['password'],
                dbname=inst.get('database', 'postgres'),
                connect_timeout=self.QUERY_TIMEOUT,
            )
        elif db_type in ('oracle', 'oracle_rac'):
            import oracledb
            dsn = f"{inst['host']}:{inst['port']}/{inst.get('service_name', inst.get('sid', 'orcl'))}"
            return oracledb.connect(
                user=inst['user'], password=inst['password'],
                dsn=dsn,
            )
        elif db_type in ('dm', 'dm8'):
            import dmpython
            return dmpython.connect(
                server=inst['host'], port=inst['port'],
                user=inst['user'], password=inst['password'],
            )
        elif db_type == 'gbase':
            import gbase8sdb
            return gbase8sdb.connect(
                host=inst['host'], port=inst['port'],
                user=inst['user'], password=inst['password'],
                database=inst.get('database', 'testdb'),
                server=inst.get('gbase_server_name', 'gbase01'),
            )
        elif db_type == 'sqlserver':
            import pyodbc
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={inst['host']},{inst['port']};"
                f"DATABASE={inst.get('database','master')};"
                f"UID={inst['user']};PWD={inst['password']};"
                f"Connect Timeout={self.QUERY_TIMEOUT};"
            )
            return pyodbc.connect(conn_str)
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")

    def _execute(self, conn, sql, db_type):
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            if cursor.description:
                columns = [col[0].lower() for col in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return rows
            return []
        finally:
            cursor.close()


# ── 全局单例获取 ──────────────────────────────────────────

_engine = None

def get_health_monitor_engine() -> HealthMonitorEngine:
    global _engine
    if _engine is None:
        _engine = HealthMonitorEngine()
    return _engine
