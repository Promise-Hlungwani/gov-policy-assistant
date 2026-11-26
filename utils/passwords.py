import bcrypt
import hashlib
import hmac

_BCRYPT_ROUNDS = 12
_BCRYPT_MAX_BYTES = 72
_DUMMY_BCRYPT_HASH = (
    b"$2b$12$IYPDps9ka2XJ59gRn12QAuzuorbAl0EzBekaRswrkhdNztubezSv2"
)
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_SIZE = 16
_HASH_SIZE = 64
_MAX_MEMORY = 64 * 1024 * 1024


def hash_password(password: str) -> str:
    if not isinstance(password, str):
        raise TypeError("Password must be text.")
    if len(password) < 12:
        raise ValueError("Passwords must be at least 12 characters long.")
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > _BCRYPT_MAX_BYTES:
        raise ValueError("Passwords must be 72 UTF-8 bytes or fewer for bcrypt.")
    return bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    ).decode("ascii")


def verify_password(password: str, encoded_hash: str | None) -> bool:
    if not isinstance(password, str) or len(password) > 1024:
        return False
    password_bytes = password.encode("utf-8")
    if not encoded_hash:
        if len(password_bytes) > _BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(password_bytes, _DUMMY_BCRYPT_HASH)
    if encoded_hash.startswith(("$2a$", "$2b$", "$2y$")):
        if len(password_bytes) > _BCRYPT_MAX_BYTES:
            return False
        try:
            return bcrypt.checkpw(password_bytes, encoded_hash.encode("ascii"))
        except ValueError:
            return False

    valid_format = True
    try:
        algorithm, salt_hex, hash_hex = encoded_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        if (
            algorithm != "scrypt"
            or len(salt) != _SALT_SIZE
            or len(expected_hash) != _HASH_SIZE
        ):
            raise ValueError("Invalid password hash.")
    except ValueError:
        valid_format = False
        salt = bytes(_SALT_SIZE)
        expected_hash = bytes(_HASH_SIZE)

    actual_hash = hashlib.scrypt(
        password_bytes,
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_HASH_SIZE,
        maxmem=_MAX_MEMORY,
    )
    return valid_format and hmac.compare_digest(actual_hash, expected_hash)
