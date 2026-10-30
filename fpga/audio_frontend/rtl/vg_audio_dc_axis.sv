// SPDX-License-Identifier: Apache-2.0
// Project-authored PCM16 DC blocker. State is signed Q24.15 (40 bits).
// Round-to-nearest, ties away from zero; no state updates on backpressure.
module vg_audio_dc_axis (
    input wire clk, input wire resetn, input wire bypass,
    input wire signed [15:0] s_data, input wire s_valid, output wire s_ready,
    output reg signed [15:0] m_data, output reg m_valid, input wire m_ready,
    output reg clipped
);
    reg signed [15:0] previous_x;
    reg signed [39:0] previous_d;
    wire signed [16:0] difference = $signed({s_data[15],s_data}) -
                                    $signed({previous_x[15],previous_x});
    wire signed [55:0] feedback_product = previous_d * 16'sd32604;
    wire signed [55:0] feedback_magnitude = feedback_product < 0 ?
                                                        -feedback_product : feedback_product;
    wire signed [55:0] feedback_rounded = (feedback_magnitude + 56'sd16384) >>> 15;
    wire signed [55:0] feedback = feedback_product < 0 ? -feedback_rounded : feedback_rounded;
    wire signed [55:0] difference_q15 = $signed({{39{difference[16]}},difference}) <<< 15;
    wire signed [56:0] state_wide = $signed({feedback[55],feedback}) +
                                                 $signed({difference_q15[55],difference_q15});
    wire state_clip = state_wide > 57'sd549755813887 || state_wide < -57'sd549755813888;
    wire signed [39:0] state_next = state_wide > 57'sd549755813887 ? 40'sh7fffffffff :
                                    state_wide < -57'sd549755813888 ? 40'sh8000000000 : state_wide[39:0];
    wire signed [40:0] state_extended = {state_next[39],state_next};
    wire signed [40:0] state_magnitude = state_extended < 0 ? -state_extended : state_extended;
    wire signed [40:0] output_magnitude = (state_magnitude + 41'sd16384) >>> 15;
    wire signed [40:0] output_wide = state_extended < 0 ? -output_magnitude : output_magnitude;
    assign s_ready = resetn && (!m_valid || m_ready);
    always @(posedge clk) begin
        if (!resetn) begin
            previous_x <= 0; previous_d <= 0; m_data <= 0; m_valid <= 0; clipped <= 0;
        end else begin
            clipped <= 0;
            if (s_ready) begin
                m_valid <= s_valid;
                if (s_valid) begin
                    previous_x <= s_data;
                    previous_d <= state_next;
                    if (bypass) m_data <= s_data;
                    else begin
                        m_data <= output_wide > 41'sd32767 ? 16'sh7fff :
                                  output_wide < -41'sd32768 ? 16'sh8000 : output_wide[15:0];
                        clipped <= state_clip || output_wide > 41'sd32767 || output_wide < -41'sd32768;
                    end
                end
            end
        end
    end
endmodule
