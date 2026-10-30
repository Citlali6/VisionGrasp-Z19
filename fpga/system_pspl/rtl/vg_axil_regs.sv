// SPDX-License-Identifier: Apache-2.0
// One outstanding transaction per direction. Register side effects occur once
// on wr_valid/rd_valid, never on BREADY/RREADY; responses remain stable stalled.
module vg_axil_regs (
    input wire clk, input wire rst_n,
    input wire [11:0] s_axi_awaddr,
    input wire s_axi_awvalid, output wire s_axi_awready,
    input wire [31:0] s_axi_wdata, input wire [3:0] s_axi_wstrb,
    input wire s_axi_wvalid, output wire s_axi_wready,
    output reg [1:0] s_axi_bresp, output reg s_axi_bvalid,
    input wire s_axi_bready,
    input wire [11:0] s_axi_araddr,
    input wire s_axi_arvalid, output wire s_axi_arready,
    output reg [31:0] s_axi_rdata, output reg [1:0] s_axi_rresp,
    output reg s_axi_rvalid, input wire s_axi_rready,
    output wire wr_valid, output wire [11:0] wr_addr,
    output wire [31:0] wr_data, output wire [3:0] wr_strb,
    input wire wr_error,
    output wire rd_valid, output wire [11:0] rd_addr,
    input wire [31:0] rd_data, input wire rd_error
);
    reg aw_held, w_held;
    reg [11:0] aw_saved;
    reg [31:0] w_saved;
    reg [3:0] strb_saved;
    wire write_fire = aw_held && w_held && !s_axi_bvalid;
    wire read_fire = s_axi_arvalid && s_axi_arready;
    assign s_axi_awready = rst_n && !aw_held && !s_axi_bvalid;
    assign s_axi_wready = rst_n && !w_held && !s_axi_bvalid;
    assign s_axi_arready = rst_n && !s_axi_rvalid;
    assign wr_valid = rst_n && write_fire && aw_saved[1:0] == 0;
    assign wr_addr = aw_saved;
    assign wr_data = w_saved;
    assign wr_strb = strb_saved;
    assign rd_valid = rst_n && read_fire && s_axi_araddr[1:0] == 0;
    assign rd_addr = s_axi_araddr;
    always @(posedge clk) begin
        if (!rst_n) begin
            aw_held <= 0; w_held <= 0; aw_saved <= 0;
            w_saved <= 0; strb_saved <= 0;
            s_axi_bvalid <= 0; s_axi_bresp <= 0;
            s_axi_rvalid <= 0; s_axi_rresp <= 0; s_axi_rdata <= 0;
        end else begin
            if (s_axi_bvalid && s_axi_bready) s_axi_bvalid <= 0;
            if (s_axi_rvalid && s_axi_rready) s_axi_rvalid <= 0;
            if (s_axi_awvalid && s_axi_awready) begin
                aw_held <= 1; aw_saved <= s_axi_awaddr;
            end
            if (s_axi_wvalid && s_axi_wready) begin
                w_held <= 1; w_saved <= s_axi_wdata; strb_saved <= s_axi_wstrb;
            end
            if (write_fire) begin
                aw_held <= 0; w_held <= 0; s_axi_bvalid <= 1;
                s_axi_bresp <= aw_saved[1:0] != 0 || wr_error ? 2'b10 : 2'b00;
            end
            if (read_fire) begin
                s_axi_rvalid <= 1;
                s_axi_rdata <= s_axi_araddr[1:0] == 0 ? rd_data : 32'b0;
                s_axi_rresp <= s_axi_araddr[1:0] != 0 || rd_error ? 2'b10 : 2'b00;
            end
        end
    end
endmodule
