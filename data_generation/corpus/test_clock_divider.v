// ============================================================================
// Programmable Clock Divider
// Generates a divided clock output from a high-frequency system clock
// Division ratio is configurable via DIV_RATIO parameter
// 50% duty cycle output
// ============================================================================
module clock_divider #(
    parameter DIV_RATIO = 10    // output freq = clk_in / DIV_RATIO
)(
    input  wire clk_in,
    input  wire rst_n,
    input  wire enable,
    output reg  clk_out,
    output reg  tick            // single-cycle pulse at divided rate
);

    localparam HALF = DIV_RATIO / 2;

    reg [15:0] counter;

    always @(posedge clk_in or negedge rst_n) begin
        if (!rst_n) begin
            counter <= 16'b0;
            clk_out <= 1'b0;
            tick    <= 1'b0;
        end else if (!enable) begin
            counter <= 16'b0;
            clk_out <= 1'b0;
            tick    <= 1'b0;
        end else begin
            tick <= 1'b0;
            if (counter == DIV_RATIO - 1) begin
                counter <= 16'b0;
                clk_out <= ~clk_out;
                tick    <= 1'b1;
            end else if (counter == HALF - 1) begin
                counter <= counter + 1;
                clk_out <= ~clk_out;
            end else begin
                counter <= counter + 1;
            end
        end
    end

endmodule
