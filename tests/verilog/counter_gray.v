// ============================================================================
// Gray Code Counter
// Used in CDC-safe FIFO pointer crossing between clock domains
// Only one bit changes per count transition — eliminates metastability risk
// ============================================================================
module counter_gray #(
    parameter WIDTH = 4
)(
    input  wire             clk,
    input  wire             rst_n,
    input  wire             enable,
    output reg  [WIDTH-1:0] gray_count,
    output wire [WIDTH-1:0] binary_count
);

    reg [WIDTH-1:0] binary_reg;

    // Binary to Gray conversion: G = B XOR (B >> 1)
    assign binary_count = binary_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            binary_reg <= {WIDTH{1'b0}};
            gray_count <= {WIDTH{1'b0}};
        end else if (enable) begin
            binary_reg <= binary_reg + 1'b1;
            gray_count <= (binary_reg + 1'b1) ^ ((binary_reg + 1'b1) >> 1);
        end
    end

endmodule
