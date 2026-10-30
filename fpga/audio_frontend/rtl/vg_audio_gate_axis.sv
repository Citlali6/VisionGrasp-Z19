// SPDX-License-Identifier: Apache-2.0
// Hysteretic amplitude gate. UQ1.15 gain 0..32768 includes exact unity.
// Envelope attacks immediately and decays by max(envelope/64,1) per sample.
module vg_audio_gate_axis (
    input wire clk, input wire resetn, input wire bypass,
    input wire [15:0] open_threshold, close_threshold, attack_step, release_step,
    input wire signed [15:0] s_data, input wire s_valid, output wire s_ready,
    output reg signed [15:0] m_data, output reg m_valid, input wire m_ready,
    output reg clipped
);
    reg [16:0] envelope;
    reg gate_open;
    reg [15:0] gain;
    wire signed [16:0] extended_sample = {s_data[15],s_data};
    wire [16:0] amplitude = extended_sample < 0 ? -extended_sample : extended_sample;
    wire [16:0] decay = envelope >= 64 ? envelope >> 6 : 17'd1;
    wire [16:0] decayed = envelope > decay ? envelope - decay : 17'd0;
    wire [16:0] next_envelope = amplitude > decayed ? amplitude : decayed;
    wire next_open = next_envelope >= {1'b0,open_threshold} ? 1'b1 :
                     next_envelope <= {1'b0,close_threshold} ? 1'b0 : gate_open;
    wire [16:0] raised_gain = {1'b0,gain} + {1'b0,attack_step};
    wire [15:0] next_gain = next_open ? (raised_gain >= 17'd32768 ? 16'd32768 : raised_gain[15:0]) :
                                  (gain > release_step ? gain - release_step : 16'd0);
    wire signed [32:0] product = s_data * $signed({1'b0,next_gain});
    wire signed [33:0] extended_product = {product[32],product};
    wire signed [33:0] magnitude = extended_product < 0 ? -extended_product : extended_product;
    wire signed [33:0] rounded_magnitude = (magnitude + 34'sd16384) >>> 15;
    wire signed [33:0] rounded = extended_product < 0 ? -rounded_magnitude : rounded_magnitude;
    assign s_ready = resetn && (!m_valid || m_ready);
    always @(posedge clk) begin
        if (!resetn) begin
            envelope <= 0; gate_open <= 0; gain <= 0; m_data <= 0; m_valid <= 0; clipped <= 0;
        end else begin
            clipped <= 0;
            if (s_ready) begin
                m_valid <= s_valid;
                if (s_valid) begin
                    envelope <= next_envelope; gate_open <= next_open; gain <= next_gain;
                    m_data <= bypass ? s_data : rounded > 34'sd32767 ? 16'sh7fff :
                                                     rounded < -34'sd32768 ? 16'sh8000 : rounded[15:0];
                    clipped <= !bypass && (rounded > 34'sd32767 || rounded < -34'sd32768);
                end
            end
        end
    end
endmodule
