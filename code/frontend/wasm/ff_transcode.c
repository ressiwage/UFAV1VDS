#include <libavcodec/avcodec.h>
#include <libavutil/avutil.h>
#include <libavformat/avformat.h>
#include <stdio.h>

static const int AV1_DEC_ID = 225;

static void logging(const char *fmt, ...);

static int decode_packet(AVPacket *pPacket, AVCodecContext *pCodecContext,
                         AVFrame *pFrame, long long int save_f);

int main(int argc, const char *argv[]) {
  int ret;
  if (argc < 2) {
    printf("You need to specify a media file.\n");
    return -1;
  }

  AVFormatContext *pFormatContext = avformat_alloc_context();
  if (!pFormatContext) {
    logging("ERROR could not allocate memory for Format Context");
    return -1;
  }

  if ((ret=avformat_open_input(&pFormatContext, argv[1], NULL, NULL)) != 0) {
    printf("%s\n", argv[1]);
    logging("ERROR could not open the file");
    char error_message[1024]; 
    av_strerror(ret, &error_message, 1024);
    printf("ret %d %s\n", ret, error_message);
    return -1;
  }
  printf("!\n");
  if (avformat_find_stream_info(pFormatContext, NULL) < 0) {
    logging("ERROR could not get the stream info");
    return -1;
  }
  printf("!\n");

  AVCodec *pCodec = NULL;

  AVCodecParameters *pCodecParameters = NULL;
  int video_stream_index = -1;

  for (int i = 0; i < pFormatContext->nb_streams; i++) {
    AVCodecParameters *pLocalCodecParameters = NULL;
    pLocalCodecParameters = pFormatContext->streams[i]->codecpar;
    AVCodec *pLocalCodec = NULL;

    // pLocalCodec = avcodec_find_decoder(pLocalCodecParameters->codec_id);
    printf("cid: %d\n", pLocalCodecParameters->codec_id);
    // if (pLocalCodec == NULL) {
    //   logging("ERROR unsupported codec!");

    //   continue;
    // }

    if (pLocalCodecParameters->codec_type == AVMEDIA_TYPE_VIDEO) {
      if (video_stream_index == -1 && pLocalCodecParameters->codec_id==AV1_DEC_ID) {
        video_stream_index = i;
        // pCodec = pLocalCodec;
        pCodecParameters = pLocalCodecParameters;
      }
    }
  }

  if (video_stream_index == -1) {
    logging("File %s does not contain a video stream!", argv[1]);
    return -1;
  }
  AVCodecParameters *codecpar =
      pFormatContext->streams[video_stream_index]->codecpar;


  // AVCodecContext *pCodecContext = avcodec_alloc_context3(pCodec);
  // if (!pCodecContext) {
  //   logging("failed to allocated memory for AVCodecContext");
  //   return -1;
  // }

  // if (avcodec_parameters_to_context(pCodecContext, pCodecParameters) < 0) {
  //   logging("failed to copy codec params to codec context");
  //   return -1;
  // }

  // AVDictionary *codec_options = NULL;
  // av_dict_set(&codec_options, "preset", "ultrafast", 0);

  // if (avcodec_open2(pCodecContext, pCodec, &codec_options) < 0) {
  //   logging("failed to open codec through avcodec_open2");
  //   return -1;
  // }

  AVFrame *pFrame = av_frame_alloc();
  if (!pFrame) {
    logging("failed to allocate memory for AVFrame");
    return -1;
  }

  AVPacket *pPacket = av_packet_alloc();
  if (!pPacket) {
    logging("failed to allocate memory for AVPacket");
    return -1;
  }
  
  AVFormatContext *input_format_context = NULL;
  AVFormatContext *output_format_context = NULL;

  avformat_alloc_output_context2(&output_format_context, NULL, "obu",
                                 "packets.obu");
  if (!output_format_context) {
    fprintf(stderr, "Could not create output context\n");
    ret = AVERROR_UNKNOWN;
    goto end;
  }
  avcodec_parameters_to_context(input_format_context, pCodecParameters);

  AVStream *out_stream = avformat_new_stream(output_format_context, NULL);
  if (!out_stream) {
    fprintf(stderr, "Failed to allocate output stream\n");
    ret = AVERROR_UNKNOWN;
    goto end;
  }

  if ((ret = avcodec_parameters_copy(out_stream->codecpar, codecpar)) < 0) {
    fprintf(stderr, "Failed to copy codec parameters\n");
    goto end;
  }

  if (!(output_format_context->oformat->flags & AVFMT_NOFILE)) {
    ret = avio_open(&output_format_context->pb, "packets.obu", AVIO_FLAG_WRITE );
    if (ret < 0) {
      fprintf(stderr, "Could not open output file '%s'\n", "packets.obu");
      goto end;
    }
  }

  ret = avformat_write_header(output_format_context, NULL);
  if (ret < 0) {
    fprintf(stderr, "Error writing header: %s\n", av_err2str(ret));
    goto end;
  }

  int response = 0;
  int how_many_packets_to_process = 8;

  long long int counter = 0;
  while (av_read_frame(pFormatContext, pPacket) >= 0) {
    if (pPacket->stream_index == video_stream_index) {
      counter++;
      printf("%hu ", pPacket->data[0]);
      ret = av_interleaved_write_frame(output_format_context, pPacket);
      if (ret < 0) {
        fprintf(stderr, "Error writing packet: %s\n", av_err2str(ret));
        break;
      }
    }

    av_packet_unref(pPacket);
  }
  av_write_trailer(output_format_context);

  logging("releasing all the resources");
end:
  printf("ret %d\n", ret);
  if (output_format_context &&
    !(output_format_context->oformat->flags & AVFMT_NOFILE))
  ret=avio_closep(&output_format_context->pb);
  printf("ret %d\n", ret);
  avformat_close_input(&pFormatContext);
  av_packet_free(&pPacket);
  av_frame_free(&pFrame);
  // avcodec_free_context(&pCodecContext);
  return 0;
}

static void logging(const char *fmt, ...) {
  va_list args;
  fprintf(stderr, "LOG: ");
  va_start(args, fmt);
  vfprintf(stderr, fmt, args);
  va_end(args);
  fprintf(stderr, "\n");
}
