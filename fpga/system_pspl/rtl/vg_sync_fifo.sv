// SPDX-License-Identifier: Apache-2.0
// Single clock FIFO, DEPTH >= 2. Contents are undefined when m_valid is false.
module vg_sync_fifo #(parameter integer WIDTH=32, DEPTH=16) (
    input wire clk, input wire rst_n,
    input wire [WIDTH-1:0] s_data, input wire s_valid, output wire s_ready,
    output wire [WIDTH-1:0] m_data, output wire m_valid, input wire m_ready,
    output reg [$clog2(DEPTH+1)-1:0] count
);
    localparam integer PW = $clog2(DEPTH);
    reg [WIDTH-1:0] memory [0:DEPTH-1];
    reg [PW-1:0] wp, rp;
    wire pop = m_valid && m_ready;
    wire push = s_valid && s_ready;
    assign m_valid = rst_n && count != 0;
    assign m_data = memory[rp];
    assign s_ready = rst_n && (count < DEPTH || pop);
    always @(posedge clk) begin
        if (!rst_n) begin count <= 0; wp <= 0; rp <= 0; end
        else begin
            case ({push,pop})
                2'b10: count <= count+1'b1;
                2'b01: count <= count-1'b1;
                default: ;
            endcase
            if (push) begin
                memory[wp] <= s_data;
                wp <= wp == DEPTH-1 ? 0 : wp+1'b1;
            end
            if (pop) rp <= rp == DEPTH-1 ? 0 : rp+1'b1;
        end
    end
endmodule
