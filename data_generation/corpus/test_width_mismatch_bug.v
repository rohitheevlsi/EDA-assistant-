// ============================================================================
// Width Mismatch Bug — Signal width inconsistency
// BUG: Assigns a 4-bit value to an 8-bit register without explicit extension,
//      and truncates a wide result into a narrow register
// ============================================================================
module width_mismatch_bug (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] wide_in,
    input  wire [3:0] narrow_in,
    output reg  [3:0] narrow_out,   // BUG: 8-bit value truncated to 4 bits
    output reg  [7:0] wide_out      // BUG: 4-bit value zero-extended silently
);

    reg [7:0] internal_wide;
    reg [3:0] internal_narrow;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            narrow_out     <= 4'b0;
            wide_out       <= 8'b0;
            internal_wide  <= 8'b0;
            internal_narrow <= 4'b0;
        end else begin
            // BUG: Truncation — upper 4 bits of wide_in are silently lost
            narrow_out <= wide_in;          // 8-bit -> 4-bit truncation

            // BUG: Implicit zero-extension — may hide sign issues
            wide_out <= narrow_in;          // 4-bit -> 8-bit extension

            // BUG: Accumulating with mismatched widths
            internal_wide <= internal_wide + narrow_in;   // 4-bit added to 8-bit
            internal_narrow <= internal_narrow + wide_in;  // 8-bit added to 4-bit (truncated)
        end
    end

endmodule
