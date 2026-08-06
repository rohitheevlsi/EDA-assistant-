module latch_bug (
    input wire clk,
    input wire en,
    input wire [3:0] data_in,
    output reg [3:0] data_out
);
    always @(*) begin
        if (en) begin
            data_out = data_in;  // No else branch -> inferred latch
        end
    end
endmodule
