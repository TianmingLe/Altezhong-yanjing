#pragma once

#include <stdint.h>

static constexpr uint8_t RELAY_FRAME_TYPE_JPEG_CHUNK = 0x01;
static constexpr uint8_t RELAY_FRAME_TYPE_FEATURE_VECTOR = 0x02;

static constexpr uint8_t RELAY_CODEC_ID_AUDIO_V2 = 22;
static constexpr uint8_t RELAY_CODEC_ID_FEATURE = 33;

static constexpr int RELAY_FRAME_HEADER_SIZE = 12;

struct RelayFrameHeader {
    uint8_t frame_type;
    uint8_t codec_id;
    uint16_t seq_le;
    uint32_t timestamp_ms_le;
    uint32_t payload_len_le;
};

inline void relay_frame_header_write(uint8_t *dst, const RelayFrameHeader &h)
{
    dst[0] = h.frame_type;
    dst[1] = h.codec_id;
    dst[2] = (uint8_t) (h.seq_le & 0xFF);
    dst[3] = (uint8_t) ((h.seq_le >> 8) & 0xFF);
    dst[4] = (uint8_t) (h.timestamp_ms_le & 0xFF);
    dst[5] = (uint8_t) ((h.timestamp_ms_le >> 8) & 0xFF);
    dst[6] = (uint8_t) ((h.timestamp_ms_le >> 16) & 0xFF);
    dst[7] = (uint8_t) ((h.timestamp_ms_le >> 24) & 0xFF);
    dst[8] = (uint8_t) (h.payload_len_le & 0xFF);
    dst[9] = (uint8_t) ((h.payload_len_le >> 8) & 0xFF);
    dst[10] = (uint8_t) ((h.payload_len_le >> 16) & 0xFF);
    dst[11] = (uint8_t) ((h.payload_len_le >> 24) & 0xFF);
}

inline void relay_frame_header_read(const uint8_t *src, RelayFrameHeader *out)
{
    out->frame_type = src[0];
    out->codec_id = src[1];
    out->seq_le = (uint16_t) ((uint16_t) src[2] | ((uint16_t) src[3] << 8));
    out->timestamp_ms_le = (uint32_t) ((uint32_t) src[4] | ((uint32_t) src[5] << 8) | ((uint32_t) src[6] << 16) | ((uint32_t) src[7] << 24));
    out->payload_len_le = (uint32_t) ((uint32_t) src[8] | ((uint32_t) src[9] << 8) | ((uint32_t) src[10] << 16) | ((uint32_t) src[11] << 24));
}
