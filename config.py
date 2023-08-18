
class DevelopmentConfig:
    """Development configuration."""

    SECRET_KEY = 'this_is_a_so_secret_secret_key'
    JWT_SECRET_KEY = "my-super-secret-key"  # Change this!
    DEBUG = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = "postgresql://dquyolns:HjjR51nX2czuc5YuMHi8ISaCDSn0De1c@ella.db.elephantsql.com/dquyolns"
