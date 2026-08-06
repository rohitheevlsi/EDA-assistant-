// ============================================================================
// CDC Violation Example — Unsynchronized Clock Domain Crossing
// BUG: Signal 'data_sync' is used in clk_b domain but driven by clk_a
//      without any synchronization flip-flops. This causes metastability.
// ============================================================================
module cdc_violation (
    input  wire       clk_a,    // source clock domain
    input  wire       clk_b,    // destination clock domain
    input  wire       rst_n,
    input  wire [7:0] data_in,  // data from domain A
    output reg  [7:0] data_out  // data in domain B — UNSYNCHRONIZED!
);

    reg [7:0] data_reg_a;

    // Domain A: capture data
    always @(posedge clk_a or negedge rst_n) begin
        if (!rst_n)
            data_reg_a <= 8'b0;
        else
            data_reg_a <= data_in;
    end

    // Domain B: uses data_reg_a directly — NO SYNCHRONIZER!
    // This is a CDC violation — data_reg_a can change asynchronously
    // relative to clk_b, causing metastability in data_out
    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n)
            data_out <= 8'b0;
        else
            data_out <= data_reg_a;  // BUG: direct crossing without sync FFs
    end

endmodule
