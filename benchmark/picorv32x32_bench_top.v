module picorv32_bench_top(
  input clk,
  input resetn,
  input mem_ready,
  input [31:0] mem_rdata,
  input pcpi_wr,
  input [31:0] pcpi_rd,
  input pcpi_wait,
  input pcpi_ready,
  input [31:0] irq,
  output [31:0] trap
);
genvar i;
generate
  for (i = 0; i < 32; i = i + 1) begin : cores
    wire mem_valid, mem_instr;
    wire [31:0] mem_addr, mem_wdata;
    wire [3:0] mem_wstrb;
    wire mem_la_read, mem_la_write;
    wire [31:0] mem_la_addr, mem_la_wdata;
    wire [3:0] mem_la_wstrb;
    wire pcpi_valid;
    wire [31:0] pcpi_insn, pcpi_rs1, pcpi_rs2;
    wire [31:0] eoi;
    wire trace_valid;
    wire [35:0] trace_data;
    picorv32 core(
      .clk(clk), .resetn(resetn), .trap(trap[i]),
      .mem_valid(mem_valid), .mem_instr(mem_instr), .mem_ready(mem_ready),
      .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb), .mem_rdata(mem_rdata),
      .mem_la_read(mem_la_read), .mem_la_write(mem_la_write), .mem_la_addr(mem_la_addr),
      .mem_la_wdata(mem_la_wdata), .mem_la_wstrb(mem_la_wstrb),
      .pcpi_valid(pcpi_valid), .pcpi_insn(pcpi_insn), .pcpi_rs1(pcpi_rs1), .pcpi_rs2(pcpi_rs2),
      .pcpi_wr(pcpi_wr), .pcpi_rd(pcpi_rd), .pcpi_wait(pcpi_wait), .pcpi_ready(pcpi_ready),
      .irq(irq), .eoi(eoi), .trace_valid(trace_valid), .trace_data(trace_data)
    );
  end
endgenerate
endmodule
