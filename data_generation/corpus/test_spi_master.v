// ============================================================================
// SPI Master Controller
// Supports CPOL and CPHA configuration, configurable clock divider
// 8-bit data transfers with chip-select control
// ============================================================================
module spi_master #(
    parameter CLK_DIV = 4   // SPI clock = sys_clk / (2 * CLK_DIV)
)(
    input  wire       clk,
    input  wire       rst_n,
    // Control interface
    input  wire       start,        // pulse to begin transfer
    input  wire [7:0] mosi_data,    // data to send
    input  wire       cpol,         // clock polarity
    input  wire       cpha,         // clock phase
    output reg  [7:0] miso_data,    // received data
    output reg        busy,         // transfer in progress
    output reg        done,         // pulse when transfer complete
    // SPI bus
    output reg        sclk,
    output reg        mosi,
    input  wire       miso,
    output reg        cs_n          // chip select (active low)
);

    localparam IDLE     = 3'b000,
               LEADING  = 3'b001,
               TRAILING = 3'b010,
               FINISH   = 3'b011;

    reg [2:0]  state;
    reg [7:0]  clk_counter;
    reg [2:0]  bit_count;
    reg [7:0]  shift_out;
    reg [7:0]  shift_in;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= IDLE;
            sclk        <= 1'b0;
            mosi        <= 1'b0;
            cs_n        <= 1'b1;
            busy        <= 1'b0;
            done        <= 1'b0;
            clk_counter <= 8'b0;
            bit_count   <= 3'b0;
            shift_out   <= 8'b0;
            shift_in    <= 8'b0;
            miso_data   <= 8'b0;
        end else begin
            done <= 1'b0;

            case (state)
                IDLE: begin
                    sclk <= cpol;
                    cs_n <= 1'b1;
                    busy <= 1'b0;
                    if (start) begin
                        busy      <= 1'b1;
                        cs_n      <= 1'b0;
                        shift_out <= mosi_data;
                        shift_in  <= 8'b0;
                        bit_count <= 3'd7;
                        clk_counter <= 8'b0;
                        mosi      <= mosi_data[7];
                        state     <= cpha ? LEADING : TRAILING;
                    end
                end

                LEADING: begin
                    if (clk_counter < CLK_DIV - 1) begin
                        clk_counter <= clk_counter + 1;
                    end else begin
                        clk_counter <= 8'b0;
                        sclk <= ~sclk;
                        // Sample MISO on leading edge
                        shift_in <= {shift_in[6:0], miso};
                        state <= TRAILING;
                    end
                end

                TRAILING: begin
                    if (clk_counter < CLK_DIV - 1) begin
                        clk_counter <= clk_counter + 1;
                    end else begin
                        clk_counter <= 8'b0;
                        sclk <= ~sclk;
                        if (!cpha) begin
                            // Sample MISO on trailing edge for CPHA=0
                            shift_in <= {shift_in[6:0], miso};
                        end
                        if (bit_count == 0) begin
                            state <= FINISH;
                        end else begin
                            bit_count <= bit_count - 1;
                            shift_out <= {shift_out[6:0], 1'b0};
                            mosi      <= shift_out[6];
                            state     <= LEADING;
                        end
                    end
                end

                FINISH: begin
                    sclk      <= cpol;
                    cs_n      <= 1'b1;
                    miso_data <= shift_in;
                    done      <= 1'b1;
                    busy      <= 1'b0;
                    state     <= IDLE;
                end

                default: state <= IDLE;
            endcase
        end
    end

endmodule
