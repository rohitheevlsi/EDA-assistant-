// ============================================================================
// Blocking Assignment in Sequential Block — Coding Style Bug
// BUG: Uses blocking assignment (=) inside a posedge-clocked always block
//      This can cause race conditions between parallel always blocks
//      and simulation/synthesis mismatch
// ============================================================================
module blocking_seq_bug (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] d_in,
    output reg  [7:0] stage1,
    output reg  [7:0] stage2,
    output reg  [7:0] stage3
);

    // BUG: Using blocking assignments in sequential logic
    // In simulation, stage1/stage2/stage3 all get d_in in same cycle
    // With non-blocking, it would be a proper 3-stage pipeline
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage1 = 8'b0;    // should be <=
            stage2 = 8'b0;    // should be <=
            stage3 = 8'b0;    // should be <=
        end else begin
            stage1 = d_in;    // BUG: blocking in sequential
            stage2 = stage1;  // Gets NEW value of stage1, not old
            stage3 = stage2;  // Gets NEW value of stage2, not old
        end
    end

endmodule
