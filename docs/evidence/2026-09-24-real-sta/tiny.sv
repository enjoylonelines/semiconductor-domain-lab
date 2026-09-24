// Original minimal research fixture authored for this project.
module tiny(input logic clk, input logic a, input logic b, output logic y);
  logic q;
  always_ff @(posedge clk) begin
    q <= a;
    y <= q ^ b;
  end
endmodule
