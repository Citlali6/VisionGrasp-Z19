/* SPDX-License-Identifier: Apache-2.0 */
#ifndef VISIONGRASP_PSPL_H
#define VISIONGRASP_PSPL_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct pspl_device pspl_device;
typedef struct {
    uint32_t frame_id, count, xmin, ymin, xmax, ymax;
    uint64_t sum_x, sum_y;
    uint32_t valid, config_version;
} pspl_video_stats;
/* All operations return 0 or negative errno. open never scans devices.
 * Explicit open is the only operation that maps MMIO. One owner per UIO node.
 * A failed transfer requires reset and reconfiguration before reuse. */
int pspl_open(const char *, uint32_t expected_id, size_t map_size,
              uint32_t timeout_ms, pspl_device **out);
void pspl_close(pspl_device *);
int pspl_read(pspl_device *, uint32_t offset, uint32_t *out);
int pspl_write(pspl_device *, uint32_t offset, uint32_t value);
int pspl_reset(pspl_device *);
int pspl_video_process(pspl_device *, const uint32_t *input, uint32_t *output,
                       size_t pixels, uint32_t width, uint32_t height,
                       pspl_video_stats *stats);
int pspl_audio_process(pspl_device *, const int16_t *input, int16_t *output,
                       size_t samples);
#ifdef __cplusplus
}
#endif
#endif
