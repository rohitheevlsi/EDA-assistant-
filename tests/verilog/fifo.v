module fifo #(parameter DEPTH = 8, WIDTH = 8) (
    input wire clk,
    input wire rst_n,
    input wire wr_en,
    input wire rd_en,
    input wire [WIDTH-1:0] wr_data,
    output reg [WIDTH-1:0] rd_data,
    output wire full,
    output wire empty
);
    reg [WIDTH-1:0] mem [0:DEPTH-1];
    reg [$clog2(DEPTH):0] count;
    reg [$clog2(DEPTH)-1:0] wr_ptr, rd_ptr;

    assign full  = (count == DEPTH);
    assign empty = (count == 0);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= 0; rd_ptr <= 0; count <= 0;
        end else begin
            if (wr_en && !full) begin
                mem[wr_ptr] <= wr_data;
                wr_ptr <= wr_ptr + 1;
                count <= count + 1;
            end
            if (rd_en && !empty) begin
                rd_data <= mem[rd_ptr];
                rd_ptr <= rd_ptr + 1;
                count <= count - 1;
            end
        end
    end
endmodule
