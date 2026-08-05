module multidriven_bug (
    input wire clk,
    input wire sel,
    input wire [3:0] a, b,
    output reg [3:0] y
);
    always @(posedge clk) begin
        if (sel) y <= a;   // y driven here...
    end

    always @(posedge clk) begin
        if (!sel) y <= b;  // ...and driven again here -> multi-driven net
    end
endmodule
