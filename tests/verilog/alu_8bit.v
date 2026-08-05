// ============================================================================
// 8-bit Arithmetic Logic Unit (ALU)
// Supports 8 operations: ADD, SUB, AND, OR, XOR, NOT, SHL, SHR
// Includes zero flag and carry flag outputs
// ============================================================================
module alu_8bit (
    input  wire [7:0] a,
    input  wire [7:0] b,
    input  wire [2:0] op,       // operation select
    output reg  [7:0] result,
    output reg        zero,     // result == 0
    output reg        carry     // carry/borrow out
);

    localparam OP_ADD = 3'b000,
               OP_SUB = 3'b001,
               OP_AND = 3'b010,
               OP_OR  = 3'b011,
               OP_XOR = 3'b100,
               OP_NOT = 3'b101,
               OP_SHL = 3'b110,
               OP_SHR = 3'b111;

    reg [8:0] temp;  // 9-bit to capture carry

    always @(*) begin
        temp  = 9'b0;
        carry = 1'b0;
        case (op)
            OP_ADD: begin
                temp   = {1'b0, a} + {1'b0, b};
                result = temp[7:0];
                carry  = temp[8];
            end
            OP_SUB: begin
                temp   = {1'b0, a} - {1'b0, b};
                result = temp[7:0];
                carry  = temp[8];  // borrow
            end
            OP_AND: result = a & b;
            OP_OR:  result = a | b;
            OP_XOR: result = a ^ b;
            OP_NOT: result = ~a;
            OP_SHL: begin
                temp   = {a, 1'b0};
                result = temp[7:0];
                carry  = temp[8];
            end
            OP_SHR: begin
                result = a >> 1;
                carry  = a[0];
            end
            default: result = 8'b0;
        endcase
        zero = (result == 8'b0);
    end

endmodule
