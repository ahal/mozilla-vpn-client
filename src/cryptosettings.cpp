#include "cryptosettings.h"
#include "hacl-star/Hacl_Chacha20Poly1305_32.h"

#include <QDebug>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonValue>
#include <QRandomGenerator>

constexpr int NONCE_SIZE = 12;
constexpr int MAC_SIZE = 16;

namespace {

uint64_t lastNonce = 0;

} // anonymous

// static
bool CryptoSettings::readFile(QIODevice &device, QSettings::SettingsMap &map)
{
    qDebug() << "Read the settings file";

    QByteArray version = device.read(1);
    if (version.length() != 1) {
        qDebug() << "Failed to read the version";
        return false;
    }

    switch ((CryptoSettings::Version) version.at(0)) {
    case NoEncryption:
        return readJsonFile(device, map);
    case EncryptionChachaPolyV1:
        return readEncryptedChachaPolyV1File(device, map);
    default:
        qDebug() << "Unsupported version";
        return false;
    }
}

// static
bool CryptoSettings::readJsonFile(QIODevice &device, QSettings::SettingsMap &map)
{
    QByteArray content = device.readAll();

    QJsonDocument json = QJsonDocument::fromJson(content);
    if (!json.isObject()) {
        qDebug() << "Invalid content read from the JSON file";
        return false;
    }

    QJsonObject obj = json.object();
    for (QJsonObject::const_iterator i = obj.constBegin(); i != obj.constEnd(); ++i) {
        map.insert(i.key(), i.value().toVariant());
    }

    return true;
}

// static
bool CryptoSettings::readEncryptedChachaPolyV1File(QIODevice &device, QSettings::SettingsMap &map)
{
    QByteArray nonce = device.read(NONCE_SIZE);
    if (nonce.length() != NONCE_SIZE) {
        qDebug() << "Failed to read the nonce";
        return false;
    }

    QByteArray mac = device.read(MAC_SIZE);
    if (mac.length() != MAC_SIZE) {
        qDebug() << "Failed to read the MAC";
        return false;
    }

    QByteArray ciphertext = device.readAll();
    if (ciphertext.length() == 0) {
        qDebug() << "Failed to read the ciphertext";
        return false;
    }

    uint8_t key[CRYPTO_SETTINGS_KEY_SIZE];
    if (!getKey(key)) {
        qDebug() << "Something went wrong reading the key";
        return false;
    }

    QByteArray version(1, EncryptionChachaPolyV1);
    QByteArray content(ciphertext.length(), 0x00);
    uint32_t result = Hacl_Chacha20Poly1305_32_aead_decrypt(key,
                                                            (uint8_t *) nonce.data(),
                                                            version.length(),
                                                            (uint8_t *) version.data(),
                                                            ciphertext.length(),
                                                            (uint8_t *) content.data(),
                                                            (uint8_t *) ciphertext.data(),
                                                            (uint8_t *) mac.data());
    qDebug() << "Result:" << result;
    if (result != 0) {
        return false;
    }

    QJsonDocument json = QJsonDocument::fromJson(content);
    if (!json.isObject()) {
        qDebug() << "Invalid content read from the JSON file";
        return false;
    }

    QJsonObject obj = json.object();
    for (QJsonObject::const_iterator i = obj.constBegin(); i != obj.constEnd(); ++i) {
        map.insert(i.key(), i.value().toVariant());
    }

    Q_ASSERT(NONCE_SIZE > sizeof(lastNonce));
    memcpy(&lastNonce, nonce.data(), sizeof(lastNonce));
    qDebug() << "Nonce:" << lastNonce;

    return true;
}

// static
bool CryptoSettings::writeFile(QIODevice &device, const QSettings::SettingsMap &map)
{
    qDebug() << "Writing the settings file";

    Version version = getSupportedVersion();
    if (!writeVersion(device, version)) {
        qDebug() << "Failed to write the version";
        return false;
    }

    switch (version) {
    case NoEncryption:
        return writeJsonFile(device, map);
    case EncryptionChachaPolyV1:
        return writeEncryptedChachaPolyV1File(device, map);
    default:
        qDebug() << "Unsupported version.";
        return false;
    }
}

// static
bool CryptoSettings::writeVersion(QIODevice &device, CryptoSettings::Version version)
{
    QByteArray v(1, version);
    return device.write(v) == v.length();
}

// static
bool CryptoSettings::writeJsonFile(QIODevice &device, const QSettings::SettingsMap &map)
{
    qDebug() << "Write plaintext JSON file";

    QJsonObject obj;
    for (QSettings::SettingsMap::ConstIterator i = map.begin(); i != map.end(); ++i) {
        obj.insert(i.key(), QJsonValue::fromVariant(i.value()));
    }

    QJsonDocument json;
    json.setObject(obj);
    QByteArray content = json.toJson(QJsonDocument::Compact);

    if (device.write(content) != content.length()) {
        qDebug() << "Failed to write the content";
        return false;
    }

    return true;
}

// static
bool CryptoSettings::writeEncryptedChachaPolyV1File(QIODevice &device,
                                                    const QSettings::SettingsMap &map)
{
    qDebug() << "Write encrypted file";

    QJsonObject obj;
    for (QSettings::SettingsMap::ConstIterator i = map.begin(); i != map.end(); ++i) {
        obj.insert(i.key(), QJsonValue::fromVariant(i.value()));
    }

    QJsonDocument json;
    json.setObject(obj);
    QByteArray content = json.toJson(QJsonDocument::Compact);

    qDebug() << "Incrementing nonce:" << lastNonce;
    if (++lastNonce == UINT64_MAX) {
        qDebug() << "Reset the nonce and the key.";
        resetKey();
        lastNonce = 0;
    }

    Q_ASSERT(NONCE_SIZE > sizeof(lastNonce));
    QByteArray nonce = QByteArray(NONCE_SIZE, 0x00);
    memcpy(nonce.data(), &lastNonce, sizeof(lastNonce));

    uint8_t key[CRYPTO_SETTINGS_KEY_SIZE];
    if (!getKey(key)) {
        qDebug() << "Invalid key";
        return false;
    }

    QByteArray version(1, EncryptionChachaPolyV1);
    QByteArray ciphertext(content.length(), 0x00);
    QByteArray mac(MAC_SIZE, 0x00);

    Hacl_Chacha20Poly1305_32_aead_encrypt(key,
                                          (uint8_t *) nonce.data(),
                                          version.length(),
                                          (uint8_t *) version.data(),
                                          content.length(),
                                          (uint8_t *) content.data(),
                                          (uint8_t *) ciphertext.data(),
                                          (uint8_t *) mac.data());

    if (device.write(nonce) != nonce.length()) {
        qDebug() << "Failed to write the nonce";
        return false;
    }

    if (device.write(mac) != mac.length()) {
        qDebug() << "Failed to write the MAC";
        return false;
    }

    if (device.write(ciphertext) != ciphertext.length()) {
        qDebug() << "Failed to write the cipher";
        return false;
    }

    return true;
}
