`timescale 1ns/1ps
// SPDX-License-Identifier: Apache-2.0
// Offline RTL verification only. No board, camera, voice or actuator model.
module tb_sort_guard;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0, external_busy=0;
    reg [11:0] awaddr=0, araddr=0;
    reg awvalid=0, wvalid=0, bready=0, arvalid=0, rready=0;
    reg [31:0] wdata=0;
    reg [3:0] wstrb=0;
    wire awready,wready,bvalid,arready,rvalid,permit;
    wire [1:0] bresp,rresp;
    wire [31:0] rdata;
    vg_sort_guard_axi dut (
        .clk(clk),.rst_n(rst_n),.external_busy(external_busy),
        .s_axi_awaddr(awaddr),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
        .s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
        .s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
        .s_axi_araddr(araddr),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
        .s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rvalid(rvalid),.s_axi_rready(rready),
        .permit_pulse(permit)
    );

    // A second core lets the test hit exact timeout/cancel/busy edges without
    // relying on the multi-cycle AXI transaction schedule.
    reg ca=0, cc=0, cx=0, cf=0, cbusy=0;
    reg [31:0] cjob=1, cbase=0, ctimeout=1000, cseq=0, cmask=100, cfjob=1;
    reg [15:0] crequired=3, cxmin=30, cymin=40, cxmax=50, cymax=60;
    reg cv=1, cffresh=1;
    wire ca_allowed,cf_allowed,cx_allowed,cactive,cready,cconsumed,ctimed,ccancelled,cpermit;
    wire [31:0] cactivejob,clastseq,cage,cpermits,cpermitjob;
    wire [15:0] cstable;
    wire [3:0] creason;
    vg_sort_guard_core direct (
        .clk(clk),.rst_n(rst_n),.busy(cbusy),.arm(ca),.cancel(cc),.consume(cx),.frame_commit(cf),
        .cfg_job(cjob),.cfg_baseline(cbase),.cfg_min_mask(32'd10),.cfg_max_mask(32'd1000),
        .cfg_timeout(ctimeout),.cfg_xmin(16'd10),.cfg_ymin(16'd20),
        .cfg_xmax(16'd100),.cfg_ymax(16'd120),.cfg_required(crequired),.cfg_jitter(16'd2),
        .frame_seq(cseq),.frame_mask(cmask),.frame_job(cfjob),
        .frame_xmin(cxmin),.frame_ymin(cymin),.frame_xmax(cxmax),.frame_ymax(cymax),
        .frame_valid(cv),.frame_fresh(cffresh),
        .arm_allowed(ca_allowed),.frame_allowed(cf_allowed),.consume_allowed(cx_allowed),
        .active(cactive),.ready(cready),.consumed(cconsumed),.timed_out(ctimed),.cancelled(ccancelled),
        .permit_pulse(cpermit),.active_job(cactivejob),.last_seq(clastseq),.age_cycles(cage),
        .permit_count(cpermits),.permit_job(cpermitjob),.stable_count(cstable),.last_reason(creason)
    );
    integer checks=0, writes=0, reads=0, axipulses=0, corepulses=0;
    reg previous_permit=0, previous_cpermit=0;
    always @(posedge clk) begin
        if (!rst_n) begin previous_permit<=0; previous_cpermit<=0; end
        else begin
            if (permit && previous_permit) $fatal(1,"AXI permit longer than one cycle");
            if (cpermit && previous_cpermit) $fatal(1,"core permit longer than one cycle");
            if (permit) axipulses=axipulses+1;
            if (cpermit) corepulses=corepulses+1;
            previous_permit<=permit; previous_cpermit<=cpermit;
        end
    end
    initial begin #20000000; $fatal(1,"SORT_GUARD_TIMEOUT"); end
    task automatic check;
        input condition; input [8*160-1:0] message;
        begin checks=checks+1; if(condition !== 1'b1) $fatal(1,"CHECK %0d: %0s",checks,message); end
    endtask
    task automatic tick;
        begin @(posedge clk); #1; end
    endtask
    task automatic wr;
        input [11:0] address; input [31:0] data; input [3:0] strobe;
        input integer aw_delay,w_delay,stall; input [1:0] response;
        integer i;
        begin
            fork
                begin
                    repeat(aw_delay) @(negedge clk);
                    @(negedge clk); awaddr=address; awvalid=1;
                    @(posedge clk); while(!awready) @(posedge clk);
                    @(negedge clk); awvalid=0;
                end
                begin
                    repeat(w_delay) @(negedge clk);
                    @(negedge clk); wdata=data; wstrb=strobe; wvalid=1;
                    @(posedge clk); while(!wready) @(posedge clk);
                    @(negedge clk); wvalid=0;
                end
            join
            while(!bvalid) @(negedge clk);
            check(bresp===response,"write response");
            for(i=0;i<stall;i=i+1) begin
                tick(); check(bvalid && bresp===response,"B response held under stall");
                check(!awready && !wready,"no second write while B stalled");
            end
            @(negedge clk); bready=1;
            @(posedge clk);
            @(negedge clk); bready=0;
            writes=writes+1;
        end
    endtask
    task automatic put;
        input [11:0] address; input [31:0] data;
        begin wr(address,data,4'hf,0,0,0,0); end
    endtask
    task automatic rd;
        input [11:0] address; input integer stall; input [1:0] response;
        output [31:0] value;
        integer i;
        begin
            @(negedge clk); araddr=address; arvalid=1;
            @(posedge clk); while(!arready) @(posedge clk);
            @(negedge clk); arvalid=0;
            while(!rvalid) @(negedge clk);
            value=rdata; check(rresp===response,"read response");
            for(i=0;i<stall;i=i+1) begin
                tick(); check(rvalid && rdata===value && rresp===response,"R payload held under stall");
                check(!arready,"no second read while R stalled");
            end
            @(negedge clk); rready=1;
            @(posedge clk);
            @(negedge clk); rready=0;
            reads=reads+1;
        end
    endtask
    task automatic expect_reg;
        input [11:0] address; input [31:0] expected;
        reg [31:0] value;
        begin rd(address,0,0,value); check(value===expected,"register value"); end
    endtask
    task automatic configure;
        input [31:0] job,baseline; input [15:0] required;
        begin
            put('h040,job); put('h044,baseline);
            put('h048,10);put('h04c,20);put('h050,100);put('h054,120);
            put('h058,10);put('h05c,1000);put('h060,required);put('h064,2);put('h068,50000);
        end
    endtask
    task automatic frame;
        input [31:0] job,seq,mask; input [15:0] x0,y0,x1,y1;
        input [1:0] flags; input [1:0] response;
        begin
            put('h080,seq);put('h084,mask);put('h088,x0);put('h08c,y0);
            put('h090,x1);put('h094,y1);put('h098,flags);put('h09c,job);
            wr('h008,8,4'hf,0,0,0,response);
        end
    endtask
    task automatic good;
        input [31:0] job,seq;
        begin frame(job,seq,100,30,40,50,60,3,0); end
    endtask
    task automatic start_core;
        input [31:0] job,timeout_value,baseline; input [15:0] required;
        begin
            @(negedge clk); cjob=job;cfjob=job;ctimeout=timeout_value;cbase=baseline;crequired=required;
            ca=1; tick(); check(cactive && cage==0 && cstable==0,"core ARM snapshot");
            @(negedge clk); ca=0;
        end
    endtask
    task automatic send_core;
        input [31:0] seq; input [15:0] x0; input valid,fresh;
        begin
            @(negedge clk); cseq=seq;cxmin=x0;cv=valid;cffresh=fresh;cf=1;
            tick(); @(negedge clk); cf=0;
        end
    endtask
    task automatic cancel_core;
        begin @(negedge clk); cc=1;tick();@(negedge clk);cc=0;end
    endtask
    reg [31:0] value, age_before, previous_count;
    integer i;
    initial begin
        repeat(4) tick(); @(negedge clk);rst_n=1;
        expect_reg('h000,'h31444753);expect_reg('h004,'h00010000);expect_reg('h010,0);
        wr('h008,1,4'hf,0,0,0,2); // unconfigured ARM
        wr('h008,4,4'hf,0,0,0,2); // idle consume
        wr('h040,17,4'hf,0,6,5,0); // AW then W, stalled B
        wr('h044,10,4'hf,6,0,3,0); // W then AW
        rd('h040,5,0,value);check(value==17,"decoupled write retained data");
        wr('h040,99,4'h0,0,0,0,2);expect_reg('h040,17);
        wr('h040,99,4'h1,0,0,0,2);expect_reg('h040,17);
        wr('h041,99,4'hf,0,0,0,2);
        wr('h070,99,4'hf,0,0,0,2);
        wr('h000,99,4'hf,0,0,0,2);
        wr('h048,'h10000,4'hf,0,0,0,2);
        wr('h098,4,4'hf,0,0,0,2);
        wr('h00c,2,4'hf,0,0,0,2);
        wr('h008,3,4'hf,0,0,0,2);
        rd('h003,4,2,value);check(value==0,"unaligned read returns zero");
        rd('h070,0,2,value);
        rd('h010,0,0,value);check(value[6],"illegal accesses set bus_fault");
        put('h008,16);expect_reg('h010,0);
        configure(17,10,3);
        // Invalid configuration is rejected at ARM, without starting a task.
        put('h048,101);wr('h008,1,4'hf,0,0,0,2);put('h048,10);
        put('h058,0);wr('h008,1,4'hf,0,0,0,2);put('h058,10);
        put('h05c,9);wr('h008,1,4'hf,0,0,0,2);put('h05c,1000);
        put('h060,0);wr('h008,1,4'hf,0,0,0,2);put('h060,3);
        put('h068,0);wr('h008,1,4'hf,0,0,0,2);put('h068,50000);
        put('h040,0);wr('h008,1,4'hf,0,0,0,2);put('h040,17);
        put('h008,16);put('h008,1);expect_reg('h014,17);expect_reg('h018,10);
        put('h048,80);put('h040,99); // active snapshot must remain original
        wr('h008,1,4'hf,0,0,0,2);expect_reg('h014,17);
        good(17,11);expect_reg('h01c,1);
        rd('h020,0,0,age_before);
        good(17,11);expect_reg('h01c,1);
        rd('h020,0,0,value);check(value>age_before,"duplicate does not refresh age");
        good(17,10);expect_reg('h01c,1);expect_reg('h018,11);
        good(17,32'h8000000b);expect_reg('h018,11);
        frame(99,12,100,30,40,50,60,3,2);expect_reg('h018,11);
        good(17,15);expect_reg('h01c,2);
        rd('h020,8,0,age_before);rd('h020,0,0,value);
        check(value>age_before,"stalled age read is a snapshot while core keeps ticking");
        wr('h008,1,4'hf,0,0,4,2);expect_reg('h01c,2);
        frame(17,20,100,32,42,52,62,3,0);expect_reg('h01c,3);
        rd('h010,0,0,value);check(value[1] && value[0],"ready after three new frames");
        good(17,21);expect_reg('h01c,3); // saturate at requirement
        frame(17,22,0,30,40,50,60,3,0);expect_reg('h01c,0);expect_reg('h02c,4);
        rd('h010,0,0,value);check(!value[1],"bad frame revokes ready");
        good(17,23);good(17,24);
        frame(17,25,100,33,40,50,60,3,0);expect_reg('h01c,0);expect_reg('h02c,5);
        good(17,26);expect_reg('h01c,1);
        frame(17,27,100,9,40,50,60,3,0);expect_reg('h01c,0);
        good(17,28);frame(17,29,100,30,40,101,60,3,0);expect_reg('h01c,0);
        good(17,30);frame(17,31,100,51,40,50,60,3,0);expect_reg('h01c,0);
        good(17,32);frame(17,33,1001,30,40,50,60,3,0);expect_reg('h01c,0);
        good(17,34);frame(17,35,100,30,40,50,60,1,0);expect_reg('h01c,0);
        good(17,36);frame(17,37,100,30,40,50,60,2,0);expect_reg('h01c,0);
        good(17,38);good(17,39);good(17,40);
        wr('h008,4,4'hf,3,0,6,0);
        expect_reg('h024,1);expect_reg('h028,17);expect_reg('h01c,0);
        rd('h010,0,0,value);check(value[3] && !value[0] && !value[1],"consume ends task");
        wr('h008,4,4'hf,0,0,0,2);expect_reg('h024,1);
        frame(17,41,100,30,40,50,60,3,2);expect_reg('h024,1);
        configure(18,41,1);put('h008,1);good(18,42);
        put('h008,2);expect_reg('h024,1);expect_reg('h01c,0);
        rd('h010,0,0,value);check(value[5] && !value[0] && !value[1],"cancel revokes task");
        configure(19,42,1);put('h008,1);good(19,43);put('h00c,1);
        rd('h010,0,0,value);check(value[2] && value[5] && !value[0] && !value[1],"software busy cancels");
        wr('h008,4,4'hf,0,0,0,2);wr('h008,1,4'hf,0,0,0,2);
        put('h008,2);expect_reg('h02c,8); // CANCEL also accepted while busy/idle
        put('h00c,0);rd('h010,0,0,value);check(!value[0],"busy clear cannot rearm");
        configure(20,43,1);put('h008,1);good(20,44);
        @(negedge clk);external_busy=1;tick();
        check(!dut.active && !dut.ready,"external busy revokes ready");
        @(negedge clk);external_busy=0;
        expect_reg('h024,1);
        configure(21,44,1);put('h008,1);
        frame(20,45,100,30,40,50,60,3,2);expect_reg('h01c,0);
        good(21,46);put('h008,4);expect_reg('h024,2);expect_reg('h028,21);

        // Exact-cycle core scenarios: timeout is an exclusive deadline.
        start_core(501,5,0,1);
        for(i=1;i<5;i=i+1) begin tick();check(cactive && cage==i,"timeout pre-boundary");end
        tick();check(!cactive && ctimed && cage==5,"timeout at exact cycle");
        start_core(502,12,0,1);send_core(1,30,1,1);
        check(cready && cage==0,"fresh frame resets age");
        while(cage<11) tick();
        @(negedge clk);cx=1;cf=1;cseq=2;
        check(!cx_allowed && !cf_allowed,"deadline disallows consume and frame");
        tick();check(ctimed && !cpermit && !cactive,"timeout wins simultaneous consume/new frame");
        @(negedge clk);cx=0;cf=0;
        start_core(503,12,0,1);send_core(1,30,1,1);
        send_core(1,30,1,1);check(cage!=0 && cstable==1,"direct duplicate ignores freshness");
        send_core(0,30,1,1);check(clastseq==1,"direct old sequence ignored");
        while(cactive) tick();check(ctimed,"duplicates cannot prevent timeout");
        start_core(504,20,0,2);send_core(1,30,1,1);
        age_before=cage;send_core(2,30,0,1);
        check(cage>age_before && cstable==0 && clastseq==2,"invalid advances seq but not freshness");
        send_core(3,30,1,0);check(cage!=0 && cstable==0,"nonfresh frame cannot reset age");
        cancel_core();check(ccancelled && !cactive,"direct cancel");
        start_core(505,1000,32'hfffffffe,2);
        send_core(32'hffffffff,30,1,1);send_core(0,30,1,1);
        check(cready && clastseq==0 && cstable==2,"32-bit sequence wrap accepted");
        send_core(32'hffffffff,30,1,1);check(clastseq==0 && cstable==2,"wrapped older sequence ignored");
        send_core(32'h80000000,30,1,1);check(clastseq==0,"half-space ambiguous jump ignored");
        @(negedge clk);cx=1;cbusy=1;tick();
        check(!cpermit && !cactive && ccancelled && creason==8,"busy wins consume");
        @(negedge clk);cx=0;cbusy=0;
        start_core(506,1000,0,4);
        send_core(1,30,1,1);send_core(2,31,1,1);send_core(3,32,1,1);
        check(cstable==3,"bounded anchor variation accepted");
        send_core(4,33,1,1);check(cstable==0 && !cready && creason==5,"slow drift against fixed anchor rejected");
        cancel_core();start_core(507,1000,0,1);send_core(1,30,1,1);
        @(negedge clk);cx=1;cc=1;tick();check(!cpermit && ccancelled && !cactive,"cancel wins consume");
        @(negedge clk);cx=0;cc=0;
        start_core(508,1000,0,1);send_core(1,30,1,1);
        @(negedge clk);cx=1;tick();
        check(cpermit && cpermits==1 && cpermitjob==508 && cstable==0 && cconsumed,"direct one-shot permit");
        tick();check(!cpermit && cpermits==1,"held consume cannot repeat permit");
        @(negedge clk);cx=0;
        start_core(509,1000,1,2);
        @(negedge clk);ca=1;cjob=999;tick();
        check(cactivejob==509 && cage>0,"active ARM cannot reset job/deadline");
        @(negedge clk);ca=0;
        check(axipulses==2 && corepulses==1,"only intended permits emitted; new ARM permits a new task");

        // Both response channels can be outstanding and must reset cleanly.
        @(negedge clk);awaddr='h040;awvalid=1;wdata=88;wstrb=15;wvalid=1;araddr=0;arvalid=1;
        @(posedge clk);check(awready && wready && arready,"concurrent read/write address acceptance");
        @(negedge clk);awvalid=0;wvalid=0;arvalid=0;
        while(!bvalid || !rvalid) tick();
        check(bresp==0 && rresp==0 && rdata=='h31444753,"independent responses outstanding");
        @(negedge clk);rst_n=0;tick();
        check(!bvalid && !rvalid,"reset flushes stalled B and R responses");
        @(negedge clk);rst_n=1;

        // Reset clears pending bus transactions as well as task/permit state.
        @(negedge clk);awaddr='h040;awvalid=1;
        @(posedge clk);check(awready,"accept isolated AW before reset");
        @(negedge clk);awvalid=0;rst_n=0;
        repeat(3) tick();check(!bvalid && !rvalid && !permit && !cpermit,"reset clears response and pulse");
        @(negedge clk);rst_n=1;
        expect_reg('h024,0);expect_reg('h014,0);expect_reg('h040,0);
        @(negedge clk);wdata=55;wstrb=15;wvalid=1;
        @(posedge clk);check(wready,"accept isolated W after reset");
        @(negedge clk);wvalid=0;
        repeat(5) tick();check(!bvalid,"pre-reset AW cannot match post-reset W");
        @(negedge clk);awaddr='h044;awvalid=1;
        @(posedge clk);check(awready,"new AW matches post-reset W");
        @(negedge clk);awvalid=0;
        while(!bvalid) tick();check(bresp==0,"completed post-reset transaction");
        @(negedge clk);bready=1;tick();@(negedge clk);bready=0;
        expect_reg('h044,55);expect_reg('h040,0);
        // Reset cannot clear a signal driven by another synchronous module.
        @(negedge clk);external_busy=1;rst_n=0;
        repeat(3) tick();
        @(negedge clk);rst_n=1;
        expect_reg('h010,4);expect_reg('h00c,0);
        configure(77,55,1);
        wr('h008,1,4'hf,0,0,0,2);
        rd('h010,0,0,value);check(value[2] && !value[0],"external busy survives reset and refuses ARM");
        @(negedge clk);external_busy=0;
        put('h008,16);put('h008,1);expect_reg('h014,77);
        rd('h010,0,0,value);check(value[0] && !value[2],"ARM allowed only after external busy is removed");
        put('h008,2);
        $display("SORT_GUARD_PASS checks=%0d axi_writes=%0d axi_reads=%0d axi_permits=%0d core_permits=%0d timeout_priority=PASS reset=PASS",checks,writes,reads,axipulses,corepulses);
        $finish;
    end
endmodule
