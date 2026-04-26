#include <assert.h>
#include <stdint.h>

#include "pc/relay/protocols/relay_protocol.h"

static void test_header_endianness()
{
    uint8_t buf[RELAY_FRAME_HEADER_SIZE] = {0};
    RelayFrameHeader h{};
    h.frame_type = RELAY_FRAME_TYPE_FEATURE_VECTOR;
    h.codec_id = RELAY_CODEC_ID_FEATURE;
    h.seq_le = 0x0201;
    h.timestamp_ms_le = 0x08070605;
    h.payload_len_le = 0x0d0c0b0a;

    relay_frame_header_write(buf, h);

    assert(buf[0] == RELAY_FRAME_TYPE_FEATURE_VECTOR);
    assert(buf[1] == RELAY_CODEC_ID_FEATURE);
    assert(buf[2] == 0x01);
    assert(buf[3] == 0x02);
    assert(buf[4] == 0x05);
    assert(buf[5] == 0x06);
    assert(buf[6] == 0x07);
    assert(buf[7] == 0x08);
    assert(buf[8] == 0x0a);
    assert(buf[9] == 0x0b);
    assert(buf[10] == 0x0c);
    assert(buf[11] == 0x0d);

    RelayFrameHeader out{};
    relay_frame_header_read(buf, &out);
    assert(out.frame_type == h.frame_type);
    assert(out.codec_id == h.codec_id);
    assert(out.seq_le == h.seq_le);
    assert(out.timestamp_ms_le == h.timestamp_ms_le);
    assert(out.payload_len_le == h.payload_len_le);
}

int main()
{
    test_header_endianness();
    return 0;
}
