#pragma once

#include <stddef.h>
#include <stdint.h>

typedef void (*relay_result_cb)(const char *session_id, const uint8_t *result, size_t len);

int relay_init(const char *ws_url, relay_result_cb cb);
int relay_send_frame(const char *session_id, const uint8_t *data, size_t len);
int relay_resume_session(const char *session_id, uint32_t last_ack_offset);
void relay_shutdown();

