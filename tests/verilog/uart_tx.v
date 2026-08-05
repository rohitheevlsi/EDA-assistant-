// ============================================================================
// UART Transmitter — 8N1 format (8 data, no parity, 1 stop)
// Configurable baud rate via CLKS_PER_BIT parameter
// ============================================================================
module uart_tx #(
    parameter CLKS_PER_BIT = 868   // 100 MHz / 115200 baud ≈ 868
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,     // pulse to begin transmission
    input  wire [7:0] tx_data,      // byte to transmit
    output reg        tx_out,       // serial output line
    output reg        tx_busy,      // high while transmitting
    output reg        tx_done       // pulse when byte fully sent
);

    localparam IDLE  = 3'b000,
               START = 3'b001,
               DATA  = 3'b010,
               STOP  = 3'b011,
               CLEANUP = 3'b100;

    reg [2:0]  state;
    reg [15:0] clk_count;
    reg [2:0]  bit_index;
    reg [7:0]  tx_shift;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= IDLE;
            tx_out    <= 1'b1;    // idle line is HIGH
            tx_busy   <= 1'b0;
            tx_done   <= 1'b0;
            clk_count <= 16'b0;
            bit_index <= 3'b0;
            tx_shift  <= 8'b0;
        end else begin
            tx_done <= 1'b0;  // default: clear done pulse

            case (state)
                IDLE: begin
                    tx_out  <= 1'b1;
                    tx_busy <= 1'b0;
                    if (tx_start) begin
                        tx_busy  <= 1'b1;
                        tx_shift <= tx_data;
                        state    <= START;
                        clk_count <= 16'b0;
                    end
                end

                START: begin
                    tx_out <= 1'b0;  // start bit = LOW
                    if (clk_count < CLKS_PER_BIT - 1) begin
                        clk_count <= clk_count + 1;
                    end else begin
                        clk_count <= 16'b0;
                        bit_index <= 3'b0;
                        state     <= DATA;
                    end
                end

                DATA: begin
                    tx_out <= tx_shift[bit_index];
                    if (clk_count < CLKS_PER_BIT - 1) begin
                        clk_count <= clk_count + 1;
                    end else begin
                        clk_count <= 16'b0;
                        if (bit_index < 7) begin
                            bit_index <= bit_index + 1;
                        end else begin
                            state <= STOP;
                        end
                    end
                end

                STOP: begin
                    tx_out <= 1'b1;  // stop bit = HIGH
                    if (clk_count < CLKS_PER_BIT - 1) begin
                        clk_count <= clk_count + 1;
                    end else begin
                        clk_count <= 16'b0;
                        tx_done   <= 1'b1;
                        state     <= CLEANUP;
                    end
                end

                CLEANUP: begin
                    tx_busy <= 1'b0;
                    state   <= IDLE;
                end

                default: state <= IDLE;
            endcase
        end
    end

endmodule
