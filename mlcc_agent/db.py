import os
import logging
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

class DBPoolManager:
    """애플리케이션 전체에서 단 하나의 커넥션 풀만 관리하기 위한 클래스입니다."""
    _pool = None

    @classmethod
    def initialize(cls):
        """환경 변수를 읽어와 커넥션 풀을 초기화합니다. (앱 시작 시 1회만 호출)"""
        if cls._pool is None:
            host = os.getenv('MLCC_DESIGN_DB_HOST')
            dbname = os.getenv('MLCC_DESIGN_DB_NAME')
            user = os.getenv('MLCC_DESIGN_DB_USER')
            password = os.getenv('MLCC_DESIGN_DB_PASSWORD')
            port = os.getenv('MLCC_DESIGN_DB_PORT')

            try:
                # minconn: 최소 유지할 연결 수 / maxconn: 최대 허용할 연결 수 (100 이하로 제한)
                cls._pool = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=50,  # 상대방 DB 보호를 위해 100보다 넉넉히 작은 50으로 설정
                    host=host,
                    dbname=dbname,
                    user=user,
                    password=password,
                    port=port
                )
                logging.info(f"DB Connection Pool initialized. (Max connections: 50)")
            except Exception as e:
                logging.error(f"[DB Error] Pool initialization failed: {e}")
                raise

    @classmethod
    def get_connection(cls):
        """풀에서 사용 가능한 커넥션을 하나 빌려옵니다."""
        if cls._pool is None:
            cls.initialize() # 풀이 없으면 생성
        return cls._pool.getconn()

    @classmethod
    def release_connection(cls, conn):
        """사용한 커넥션을 풀에 반납합니다."""
        if cls._pool and conn:
            cls._pool.putconn(conn)

    @classmethod
    def close_all(cls):
        """프로그램 종료 시 풀에 있는 모든 커넥션을 안전하게 닫습니다."""
        if cls._pool:
            cls._pool.closeall()
            logging.info("All DB connections in the pool have been closed.")


class DatabaseHandler:
    """실제 쿼리를 실행하는 핸들러 클래스입니다."""
    
    def execute_read(self, query, params=None):
        """SELECT 문 조회용"""
        # 1. 풀에서 커넥션 대여
        conn = DBPoolManager.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"[DB Error] Read query failed: {e}")
            return None
        finally:
            # 2. 에러가 나든 성공하든 무조건 풀에 커넥션 반납 ★★★ (가장 중요)
            DBPoolManager.release_connection(conn)

    def execute_write(self, query, params=None):
        """INSERT, UPDATE, DELETE 문 변경용"""
        conn = DBPoolManager.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logging.error(f"[DB Error] Write query failed: {e}")
            return False
        finally:
            # 작업이 끝나면 무조건 풀에 반납
            DBPoolManager.release_connection(conn)

db = DatabaseHandler()