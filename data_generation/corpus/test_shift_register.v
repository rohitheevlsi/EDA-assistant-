// ============================================================================
// Universal Shift Register (8-bit)
// Supports: Parallel Load, Shift Left, Shift Right, Hold
// Used in serial-parallel conversion, data serialization
// ============================================================================
module shift_register #(
    parameter WIDTH = 8
)(
    input  wire             clk,
    input  wire             rst_n,
    input  wire [1:0]       mode,       // 00=Hold, 01=Shift Left, 10=Shift Right, 11=Parallel Load
    input  wire             serial_in,  // serial input for shifts
    input  wire [WIDTH-1:0] parallel_in,// parallel load data
    output reg  [WIDTH-1:0] data_out,   // current register contents
    output wire             serial_out_msb, // MSB serial output (for shift-left)
    output wire             serial_out_lsb  // LSB serial output (for shift-right)
);

    localparam MODE_HOLD  = 2'b00,
               MODE_SHL   = 2'b01,
               MODE_SHR   = 2'b10,
               MODE_LOAD  = 2'b11;

    assign serial_out_msb = data_out[WIDTH-1];
    assign serial_out_lsb = data_out[0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= {WIDTH{1'b0}};
        end else begin
            case (mode)
                MODE_HOLD: data_out <= data_out;
                MODE_SHL:  data_out <= {data_out[WIDTH-2:0], serial_in};
                MODE_SHR:  data_out <= {serial_in, data_out[WIDTH-1:1]};
                MODE_LOAD: data_out <= parallel_in;
                default:   data_out <= data_out;
            endcase
        end
    end

endmodule
