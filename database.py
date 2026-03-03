# -*- coding: utf-8 -*-
"""
数据库管理模块
v2.3.0 - SQLAlchemy数据库集成
"""

import os
from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging

from models import Base, BattleRecord, AgentMemory, AuditRule, SystemMetrics, SystemAlert, CollaborativeSession

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    """
    数据库管理器
    支持SQLite和PostgreSQL
    """
    
    def __init__(self, db_url=None, echo=False):
        """
        初始化数据库连接
        
        Args:
            db_url: 数据库URL
                - SQLite: sqlite:///./digital_twin.db
                - PostgreSQL: postgresql://user:pass@localhost/dbname
            echo: 是否打印SQL语句
        """
        # 从环境变量或使用默认值
        if db_url is None:
            db_url = os.getenv('DATABASE_URL', 'sqlite:///./digital_twin.db')
        
        self.db_url = db_url
        self.is_sqlite = db_url.startswith('sqlite')
        self.is_postgres = db_url.startswith('postgresql')
        
        logger.info(f"Initializing database: {self._safe_url()}")
        
        # 创建引擎
        engine_kwargs = {
            'echo': echo,
            'future': True
        }
        
        # SQLite特殊配置
        if self.is_sqlite:
            engine_kwargs['connect_args'] = {
                'check_same_thread': False,  # 允许多线程
                'timeout': 20  # 超时时间
            }
            # 启用WAL模式以提升并发性能
            @event.listens_for(create_engine(db_url, **engine_kwargs), "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()
        
        # PostgreSQL连接池配置
        elif self.is_postgres:
            engine_kwargs['poolclass'] = QueuePool
            engine_kwargs['pool_size'] = 10
            engine_kwargs['max_overflow'] = 20
            engine_kwargs['pool_pre_ping'] = True
            engine_kwargs['pool_recycle'] = 3600
        
        self.engine = create_engine(db_url, **engine_kwargs)
        
        # 创建会话工厂
        self.SessionLocal = scoped_session(
            sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
        )
        
        logger.info("Database initialized successfully")
    
    def _safe_url(self):
        """返回安全的URL(隐藏密码)"""
        url = self.db_url
        if '@' in url and '://' in url:
            # 隐藏密码
            protocol, rest = url.split('://', 1)
            if '@' in rest:
                credentials, host_path = rest.split('@', 1)
                if ':' in credentials:
                    user, _ = credentials.split(':', 1)
                    return f"{protocol}://{user}:***@{host_path}"
        return url
    
    def init_db(self):
        """
        初始化数据库
        创建所有表
        """
        logger.info("Creating database tables...")
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
            
            # 验证表创建
            from sqlalchemy import inspect
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            logger.info(f"Created tables: {', '.join(tables)}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            return False
    
    def drop_all(self):
        """
        删除所有表 (危险操作!)
        """
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=self.engine)
        logger.info("All tables dropped")
    
    @contextmanager
    def get_session(self):
        """
        获取数据库会话 (上下文管理器)
        
        用法:
            with db.get_session() as session:
                user = session.query(User).first()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_db(self):
        """
        获取数据库会话 (用于依赖注入)
        
        用法:
            db = next(database.get_db())
            try:
                # use db
            finally:
                db.close()
        """
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    def execute_raw(self, sql, params=None):
        """
        执行原始SQL
        
        Args:
            sql: SQL语句
            params: 参数
        """
        with self.get_session() as session:
            result = session.execute(sql, params or {})
            return result
    
    def health_check(self):
        """
        健康检查
        返回数据库连接状态
        """
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            return {
                'status': 'healthy',
                'database': self._safe_url(),
                'type': 'sqlite' if self.is_sqlite else 'postgresql'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'database': self._safe_url()
            }
    
    def get_stats(self):
        """
        获取数据库统计信息
        """
        stats = {}
        
        try:
            with self.get_session() as session:
                # 表记录数
                stats['battle_records'] = session.query(BattleRecord).count()
                stats['agent_memories'] = session.query(AgentMemory).count()
                stats['audit_rules'] = session.query(AuditRule).count()
                stats['system_metrics'] = session.query(SystemMetrics).count()
                stats['system_alerts'] = session.query(SystemAlert).count()
                
                # 数据库大小 (仅SQLite)
                if self.is_sqlite:
                    db_file = self.db_url.replace('sqlite:///', '')
                    if os.path.exists(db_file):
                        stats['database_size_mb'] = os.path.getsize(db_file) / (1024 * 1024)
                
                return stats
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}
    
    def vacuum(self):
        """
        清理数据库 (仅SQLite)
        回收空间,优化性能
        """
        if not self.is_sqlite:
            logger.warning("VACUUM only supported for SQLite")
            return False
        
        try:
            with self.engine.connect() as conn:
                conn.execute("VACUUM")
            logger.info("Database vacuumed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            return False
    
    def backup(self, backup_path):
        """
        备份数据库 (仅SQLite)
        
        Args:
            backup_path: 备份文件路径
        """
        if not self.is_sqlite:
            logger.warning("Backup only supported for SQLite")
            return False
        
        try:
            import shutil
            db_file = self.db_url.replace('sqlite:///', '')
            shutil.copy2(db_file, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return False
    
    def migrate(self, migration_script):
        """
        执行数据库迁移脚本
        
        Args:
            migration_script: SQL迁移脚本
        """
        try:
            with self.get_session() as session:
                for statement in migration_script.split(';'):
                    statement = statement.strip()
                    if statement:
                        session.execute(statement)
            logger.info("Migration executed successfully")
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def close(self):
        """关闭数据库连接"""
        self.SessionLocal.remove()
        self.engine.dispose()
        logger.info("Database connection closed")


# 全局数据库实例
db = Database()


# 便捷函数
def init_database(db_url=None):
    """初始化数据库"""
    global db
    db = Database(db_url)
    return db.init_db()


def get_database():
    """获取数据库实例"""
    return db


# 数据访问层 (DAO) 辅助类
class BaseDAO:
    """基础DAO类"""
    
    def __init__(self, model_class):
        self.model_class = model_class
        self.db = db
    
    def create(self, **kwargs):
        """创建记录"""
        with self.db.get_session() as session:
            instance = self.model_class(**kwargs)
            session.add(instance)
            session.flush()
            session.refresh(instance)
            return instance
    
    def get_by_id(self, id):
        """根据ID获取"""
        with self.db.get_session() as session:
            return session.query(self.model_class).filter_by(id=id).first()
    
    def get_all(self, limit=None, offset=None):
        """获取所有记录"""
        with self.db.get_session() as session:
            query = session.query(self.model_class)
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            return query.all()
    
    def update(self, id, **kwargs):
        """更新记录"""
        with self.db.get_session() as session:
            instance = session.query(self.model_class).filter_by(id=id).first()
            if instance:
                for key, value in kwargs.items():
                    setattr(instance, key, value)
                session.flush()
                session.refresh(instance)
                return instance
            return None
    
    def delete(self, id):
        """删除记录"""
        with self.db.get_session() as session:
            instance = session.query(self.model_class).filter_by(id=id).first()
            if instance:
                session.delete(instance)
                return True
            return False
    
    def count(self):
        """统计记录数"""
        with self.db.get_session() as session:
            return session.query(self.model_class).count()


# 预定义DAO
battle_record_dao = BaseDAO(BattleRecord)
agent_memory_dao = BaseDAO(AgentMemory)
audit_rule_dao = BaseDAO(AuditRule)
system_metrics_dao = BaseDAO(SystemMetrics)
system_alert_dao = BaseDAO(SystemAlert)
