// SystemVerilog test module with logic types and always_ff
module custom_counter #(
    parameter WIDTH = 4
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             enable,
    output logic [WIDTH-1:0] count
);

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      count <= '0;
    end else if (enable) begin
      count <= count + 1'b1;
    end
  end

endmodule
